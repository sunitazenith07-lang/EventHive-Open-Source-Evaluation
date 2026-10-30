"""Regression coverage for event replay, refunds, and reconciliation."""

from models import new_order
from service import apply_order_event, reconcile_orders


def test_replayed_refund_event_is_not_counted_twice():
    order = new_order("R1", 3000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=3000)
    event = {"event_id": "refund-1", "type": "refund_processed", "amount_paise": 1000}
    once = apply_order_event(order, event)
    twice = apply_order_event(once, event)
    assert once["refunded_paise"] == 1000
    assert twice == once


def test_boolean_refund_amount_is_rejected():
    order = new_order("R2", 500, "REJECTED")
    order.update(payment_status="PAID", refund_due_paise=500)
    output = apply_order_event(
        order, {"event_id": "refund-2", "type": "refund_processed", "amount_paise": True}
    )
    assert output["refunded_paise"] == 0
    assert output["payment_status"] == "PAID"


def test_partial_refund_then_excess_is_rejected():
    order = new_order("R3", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    first = apply_order_event(
        order, {"event_id": "refund-3", "type": "refund_processed", "amount_paise": 4000}
    )
    second = apply_order_event(
        first, {"event_id": "refund-4", "type": "refund_processed", "amount_paise": 2000}
    )
    assert second["refunded_paise"] == 4000
    assert second["payment_status"] == "PAID"
    assert order["refunded_paise"] == 0


def test_full_refund_after_partial_marks_refunded():
    order = new_order("R4", 5000, "REJECTED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    first = apply_order_event(
        order, {"event_id": "refund-5", "type": "refund_processed", "amount_paise": 2000}
    )
    second = apply_order_event(
        first, {"event_id": "refund-6", "type": "refund_processed", "amount_paise": 3000}
    )
    assert first["payment_status"] == "PAID"
    assert second["payment_status"] == "REFUNDED"
    assert second["refunded_paise"] == 5000


def test_reconciliation_flags_amount_and_status_for_same_order():
    internal = [{"order_id": "O1", "amount_paise": 5000, "status": "PLACED"}]
    provider = [{"order_id": "O1", "amount_paise": 4500, "status": "CANCELLED"}]
    report = reconcile_orders(internal, provider)
    assert report["matched"] == []
    assert report["amount_mismatches"] == ["O1"]
    assert report["status_mismatches"] == ["O1"]
