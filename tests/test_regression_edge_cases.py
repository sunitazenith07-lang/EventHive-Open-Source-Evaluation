"""Regression and edge-case tests for OrderOps."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_payment_confirmed_after_rejection():
    """Edge Case: Late payment confirmation after restaurant rejection sets refund_due_paise."""
    order = new_order("ORD-LATE-1", 7500, "PLACED")
    rejected = apply_order_event(order, ev("E-REJ", "restaurant_rejected"))
    assert rejected["status"] == "REJECTED"
    assert rejected["payment_status"] == "UNPAID"
    assert rejected["refund_due_paise"] == 0

    paid = apply_order_event(rejected, ev("E-PAY", "payment_confirmed"))
    assert paid["status"] == "REJECTED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 7500


def test_payment_confirmed_after_cancellation():
    """Edge Case: Late payment confirmation after customer cancellation sets refund_due_paise."""
    order = new_order("ORD-LATE-2", 4200, "ACCEPTED")
    cancelled = apply_order_event(order, ev("E-CAN", "cancel_requested"))
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["payment_status"] == "UNPAID"
    assert cancelled["refund_due_paise"] == 0

    paid = apply_order_event(cancelled, ev("E-PAY", "payment_confirmed"))
    assert paid["status"] == "CANCELLED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 4200


def test_replay_with_conflicting_payload_is_ignored():
    """Edge Case: Repeated event ID with conflicting payload is ignored."""
    order = new_order("ORD-CONF", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    
    first = apply_order_event(order, ev("REF-1", "refund_processed", amount_paise=2000))
    assert first["refunded_paise"] == 2000
    assert first["processed_event_ids"] == ["REF-1"]

    # Replay same event_id with different amount
    conflicting = apply_order_event(first, ev("REF-1", "refund_processed", amount_paise=3000))
    assert conflicting["refunded_paise"] == 2000
    assert conflicting["processed_event_ids"] == ["REF-1"]


def test_event_without_event_id_handled_safely():
    """Edge Case: Missing event_id does not crash or corrupt processed_event_ids."""
    order = new_order("ORD-NOID", 5000, "PLACED")
    processed = apply_order_event(order, {"type": "restaurant_accepted"})
    assert processed["status"] == "ACCEPTED"
    assert processed["processed_event_ids"] == []


def test_reconciliation_simultaneous_amount_and_status_mismatch():
    """Edge Case: Both amount and status mismatch reported separately and not matched."""
    internal = [{"order_id": "ORD-BOTH", "amount_paise": 5000, "status": "ACCEPTED"}]
    provider = [{"order_id": "ORD-BOTH", "amount_paise": 6000, "status": "DELIVERED"}]
    report = reconcile_orders(internal, provider)
    assert report["matched"] == []
    assert report["amount_mismatches"] == ["ORD-BOTH"]
    assert report["status_mismatches"] == ["ORD-BOTH"]


def test_empty_and_malformed_records():
    """Edge Case: Empty or malformed inputs handle cleanly without error."""
    assert apply_order_event({}, {}) == {
        "status": "PLACED",
        "payment_status": "UNPAID",
        "refund_due_paise": 0,
        "refunded_paise": 0,
        "processed_event_ids": [],
    }
    assert apply_order_event(None, {}) == {}
    assert apply_order_event({"order_id": "O1"}, None) == {"order_id": "O1"}

    report = reconcile_orders(None, None)
    assert report == {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    report2 = reconcile_orders([None, "malformed", {"foo": "bar"}], [{}])
    assert report2 == {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }


def test_boundary_amounts_one_paisa():
    """Edge Case: 1 paisa order, cancellation and full refund."""
    order = new_order("ORD-1P", 1, "PLACED")
    order = apply_order_event(order, ev("E1", "payment_confirmed"))
    order = apply_order_event(order, ev("E2", "cancel_requested"))
    assert order["status"] == "CANCELLED"
    assert order["refund_due_paise"] == 1
    assert order["payment_status"] == "PAID"

    # Refund exactly 1 paisa
    order = apply_order_event(order, ev("E3", "refund_processed", amount_paise=1))
    assert order["refunded_paise"] == 1
    assert order["payment_status"] == "REFUNDED"


def test_cancellation_after_dispatch_preserves_state():
    """Edge Case: Cancellation after dispatch leaves OUT_FOR_DELIVERY status intact."""
    order = new_order("ORD-DISP", 10000, "ACCEPTED")
    order = apply_order_event(order, ev("E1", "payment_confirmed"))
    order = apply_order_event(order, ev("E2", "dispatch_started"))
    assert order["status"] == "OUT_FOR_DELIVERY"

    order_after = apply_order_event(order, ev("E3", "cancel_requested"))
    assert order_after["status"] == "OUT_FOR_DELIVERY"
    assert order_after["refund_due_paise"] == 0
    assert order_after["payment_status"] == "PAID"


def test_partial_refund_then_full_refund_sequence():
    """Edge Case: Two partial refunds summing exactly to refund_due_paise."""
    order = new_order("ORD-PART", 3000, "PLACED")
    order = apply_order_event(order, ev("P1", "payment_confirmed"))
    order = apply_order_event(order, ev("R1", "restaurant_rejected"))
    assert order["status"] == "REJECTED"
    assert order["refund_due_paise"] == 3000

    # First partial refund: 1000
    order = apply_order_event(order, ev("REF-1", "refund_processed", amount_paise=1000))
    assert order["refunded_paise"] == 1000
    assert order["payment_status"] == "PAID"

    # Second refund for remaining: 2000
    order = apply_order_event(order, ev("REF-2", "refund_processed", amount_paise=2000))
    assert order["refunded_paise"] == 3000
    assert order["payment_status"] == "REFUNDED"


def test_refund_attempt_on_delivered_order_rejected():
    """Edge Case: Refund processed event on DELIVERED order is ignored."""
    order = new_order("ORD-DELIV", 5000, "DELIVERED")
    order["payment_status"] = "PAID"
    res = apply_order_event(order, ev("REF-BAD", "refund_processed", amount_paise=5000))
    assert res["refunded_paise"] == 0
    assert res["payment_status"] == "PAID"

