"""Regression and edge-case test suite for OrderOps service."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def make_event(event_id, event_type, **extra):
    return {"event_id": event_id, "type": event_type, **extra}


def test_duplicate_event_idempotency_preserves_single_record():
    """Verify replaying an event does not append duplicate event IDs or reapply effects."""
    order = new_order("ORD-001", 1500)
    event = make_event("EVT-100", "payment_confirmed")

    applied_once = apply_order_event(order, event)
    assert applied_once["payment_status"] == "PAID"
    assert applied_once["processed_event_ids"] == ["EVT-100"]

    applied_twice = apply_order_event(applied_once, event)
    assert applied_twice["payment_status"] == "PAID"
    assert applied_twice["processed_event_ids"] == ["EVT-100"]


def test_refund_rejection_for_boolean_amount():
    """Verify bool amounts (True/False) are rejected even though bool is a subclass of int in Python."""
    order = new_order("ORD-002", 2000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=2000)

    res_true = apply_order_event(order, make_event("R-BOOL-1", "refund_processed", amount_paise=True))
    assert res_true["refunded_paise"] == 0
    assert res_true["payment_status"] == "PAID"

    res_false = apply_order_event(order, make_event("R-BOOL-2", "refund_processed", amount_paise=False))
    assert res_false["refunded_paise"] == 0
    assert res_false["payment_status"] == "PAID"


def test_cumulative_partial_refunds_transition_to_refunded_on_exact_completion():
    """Verify sequential partial refunds track due amounts and flip to REFUNDED only when exact total reached."""
    order = new_order("ORD-003", 3000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=3000)

    # Partial refund 1: 1000 paise
    step1 = apply_order_event(order, make_event("R-1", "refund_processed", amount_paise=1000))
    assert step1["refunded_paise"] == 1000
    assert step1["payment_status"] == "PAID"

    # Excess refund attempt: 2500 paise (remaining is 2000) -> must be rejected
    excess = apply_order_event(step1, make_event("R-EXCESS", "refund_processed", amount_paise=2500))
    assert excess["refunded_paise"] == 1000
    assert excess["payment_status"] == "PAID"

    # Partial refund 2: 1200 paise (remaining is 2000) -> accepted, total 2200
    step2 = apply_order_event(step1, make_event("R-2", "refund_processed", amount_paise=1200))
    assert step2["refunded_paise"] == 2200
    assert step2["payment_status"] == "PAID"

    # Final refund: 800 paise (remaining is 800) -> reaches exactly 3000 -> REFUNDED
    step3 = apply_order_event(step2, make_event("R-3", "refund_processed", amount_paise=800))
    assert step3["refunded_paise"] == 3000
    assert step3["payment_status"] == "REFUNDED"

    # Post-refund attempt: another refund event after status is REFUNDED -> must be rejected
    post = apply_order_event(step3, make_event("R-4", "refund_processed", amount_paise=100))
    assert post["refunded_paise"] == 3000
    assert post["payment_status"] == "REFUNDED"


def test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due():
    """Verify that if payment arrives after cancellation/rejection, refund_due_paise is populated."""
    # Scenario A: Cancelled then paid
    order_cancel = new_order("ORD-004A", 4500, "PLACED")
    order_cancel = apply_order_event(order_cancel, make_event("EV-CANCEL", "cancel_requested"))
    assert order_cancel["status"] == "CANCELLED"
    assert order_cancel["payment_status"] == "UNPAID"
    assert order_cancel["refund_due_paise"] == 0

    order_cancel = apply_order_event(order_cancel, make_event("EV-PAY", "payment_confirmed"))
    assert order_cancel["payment_status"] == "PAID"
    assert order_cancel["refund_due_paise"] == 4500

    # Scenario B: Rejected then paid
    order_reject = new_order("ORD-004B", 5500, "PLACED")
    order_reject = apply_order_event(order_reject, make_event("EV-REJ", "restaurant_rejected"))
    assert order_reject["status"] == "REJECTED"
    assert order_reject["payment_status"] == "UNPAID"
    assert order_reject["refund_due_paise"] == 0

    order_reject = apply_order_event(order_reject, make_event("EV-PAY2", "payment_confirmed"))
    assert order_reject["payment_status"] == "PAID"
    assert order_reject["refund_due_paise"] == 5500


def test_cancellation_after_dispatch_and_delivery_is_strictly_ignored():
    """Verify cancellation requests after dispatch or delivery are rejected."""
    order_dispatched = new_order("ORD-005", 2500, "OUT_FOR_DELIVERY")
    out1 = apply_order_event(order_dispatched, make_event("EV-C1", "cancel_requested"))
    assert out1["status"] == "OUT_FOR_DELIVERY"

    order_delivered = new_order("ORD-006", 2500, "DELIVERED")
    out2 = apply_order_event(order_delivered, make_event("EV-C2", "cancel_requested"))
    assert out2["status"] == "DELIVERED"


def test_malformed_and_none_events_do_not_corrupt_state():
    """Verify non-dict events, missing event_ids, and empty orders are handled safely."""
    order = new_order("ORD-007", 1000)

    # None event
    res1 = apply_order_event(order, None)
    assert res1 == order

    # Non-dict event
    res2 = apply_order_event(order, "invalid-event-string")
    assert res2 == order

    # Missing event_id event
    res3 = apply_order_event(order, {"type": "payment_confirmed"})
    assert res3["payment_status"] == "PAID"
    assert res3["processed_event_ids"] == []

    # Non-dict order
    res4 = apply_order_event(None, make_event("EV-1", "payment_confirmed"))
    assert res4 is None


def test_reconciliation_detects_simultaneous_amount_and_status_mismatch():
    """Verify that an order with both amount and status differences is recorded in both mismatch lists."""
    internal = [{"order_id": "ORD-DUAL", "amount_paise": 1000, "status": "PLACED"}]
    provider = [{"order_id": "ORD-DUAL", "amount_paise": 1200, "status": "DELIVERED"}]

    report = reconcile_orders(internal, provider)
    assert "ORD-DUAL" in report["amount_mismatches"]
    assert "ORD-DUAL" in report["status_mismatches"]
    assert report["matched"] == []


def test_reconciliation_with_total_paise_and_malformed_entries():
    """Verify reconciliation maps total_paise correctly and ignores non-dict or unkeyed rows."""
    internal = [
        None,
        {"status": "PLACED"},  # missing order_id
        {"order_id": "ORD-1", "total_paise": 5000, "status": "ACCEPTED"},
        {"order_id": "ORD-2", "total_paise": 2000, "status": "PLACED"},
    ]
    provider = [
        "not-a-dict",
        {"order_id": "ORD-1", "amount_paise": 5000, "status": "ACCEPTED"},
        {"order_id": "ORD-3", "amount_paise": 7000, "status": "DELIVERED"},
    ]

    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["ORD-1"]
    assert report["missing_from_provider"] == ["ORD-2"]
    assert report["missing_from_internal"] == ["ORD-3"]
    assert report["amount_mismatches"] == []
    assert report["status_mismatches"] == []
