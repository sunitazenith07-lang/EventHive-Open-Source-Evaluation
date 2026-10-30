"""Regression and edge-case tests for OrderOps order lifecycle and reconciliation."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def make_event(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_event_without_id_does_not_pollute_processed_ids():
    order = new_order("O-NONE", 3000)
    event = {"type": "payment_confirmed"}
    result = apply_order_event(order, event)
    assert result["payment_status"] == "PAID"
    assert result["processed_event_ids"] == []


def test_payment_confirmed_after_rejection_sets_refund_due():
    order = new_order("O-LATE-PAY", 4500, "PLACED")
    # First reject unpaid order
    order = apply_order_event(order, make_event("e1", "restaurant_rejected"))
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "UNPAID"
    assert order["refund_due_paise"] == 0

    # Late payment arrives
    order = apply_order_event(order, make_event("e2", "payment_confirmed"))
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 4500


def test_payment_confirmed_after_cancellation_sets_refund_due():
    order = new_order("O-CANCEL-PAY", 2500, "PLACED")
    # Cancel unpaid order
    order = apply_order_event(order, make_event("e1", "cancel_requested"))
    assert order["status"] == "CANCELLED"
    assert order["refund_due_paise"] == 0

    # Payment arrives after cancellation
    order = apply_order_event(order, make_event("e2", "payment_confirmed"))
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 2500


def test_sequential_partial_refunds_transition_to_refunded_on_exact_match():
    order = new_order("O-PARTIAL", 3000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=3000)

    # First partial refund
    order = apply_order_event(order, make_event("r1", "refund_processed", amount_paise=1000))
    assert order["refunded_paise"] == 1000
    assert order["payment_status"] == "PAID"

    # Second partial refund
    order = apply_order_event(order, make_event("r2", "refund_processed", amount_paise=1500))
    assert order["refunded_paise"] == 2500
    assert order["payment_status"] == "PAID"

    # Final partial refund completing full amount
    order = apply_order_event(order, make_event("r3", "refund_processed", amount_paise=500))
    assert order["refunded_paise"] == 3000
    assert order["payment_status"] == "REFUNDED"

    # Subsequent refund attempt after complete refund is ignored
    order = apply_order_event(order, make_event("r4", "refund_processed", amount_paise=100))
    assert order["refunded_paise"] == 3000
    assert order["payment_status"] == "REFUNDED"


def test_refund_rejected_when_exceeding_remaining_due_after_partial():
    order = new_order("O-BOUNDS", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    # Valid partial refund of 3000 (remaining: 2000)
    order = apply_order_event(order, make_event("r1", "refund_processed", amount_paise=3000))
    assert order["refunded_paise"] == 3000

    # Attempt refund of 2500 (> remaining 2000)
    order = apply_order_event(order, make_event("r2", "refund_processed", amount_paise=2500))
    assert order["refunded_paise"] == 3000
    assert order["payment_status"] == "PAID"


def test_boolean_refund_amount_rejected():
    order = new_order("O-BOOL", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    # In Python bool is an int subclass (isinstance(True, int) == True)
    order = apply_order_event(order, make_event("r1", "refund_processed", amount_paise=True))
    assert order["refunded_paise"] == 0
    order = apply_order_event(order, make_event("r2", "refund_processed", amount_paise=False))
    assert order["refunded_paise"] == 0


def test_reconcile_both_amount_and_status_mismatch():
    internal = [{"order_id": "ORD-MISMATCH", "amount_paise": 1000, "status": "PLACED"}]
    provider = [{"order_id": "ORD-MISMATCH", "amount_paise": 2000, "status": "DELIVERED"}]
    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-MISMATCH"]
    assert report["status_mismatches"] == ["ORD-MISMATCH"]
    assert report["matched"] == []


def test_reconcile_handles_total_paise_and_amount_paise_keys():
    internal = [{"order_id": "ORD-KEY", "total_paise": 5000, "status": "PLACED"}]
    provider = [{"order_id": "ORD-KEY", "amount_paise": 5000, "status": "PLACED"}]
    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["ORD-KEY"]
    assert report["amount_mismatches"] == []
    assert report["status_mismatches"] == []


def test_cancellation_after_dispatch_does_not_affect_state():
    for initial in ("OUT_FOR_DELIVERY", "DELIVERED"):
        order = new_order("O-DISPATCHED", 5000, initial)
        order["payment_status"] = "PAID"
        result = apply_order_event(order, make_event("e-cancel", "cancel_requested"))
        assert result["status"] == initial
        assert result["refund_due_paise"] == 0
