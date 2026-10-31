"""Regression tests for OrderOps bug fixes, edge cases, and stretch work."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders, summarise_orders_by_state


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_reconciliation_simultaneous_amount_and_status_mismatch():
    """An order with both amount and status mismatch must appear in both lists."""
    internal = [{"order_id": "ORD-MIX", "amount_paise": 1000, "status": "PLACED"}]
    provider = [{"order_id": "ORD-MIX", "amount_paise": 1200, "status": "DELIVERED"}]
    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-MIX"]
    assert report["status_mismatches"] == ["ORD-MIX"]
    assert report["matched"] == []


def test_reconciliation_uses_internal_total_paise():
    """Ensure internal orders using total_paise correctly reconcile with provider amount_paise."""
    internal = [new_order("ORD-001", 4500, "PLACED")]
    provider = [{"order_id": "ORD-001", "amount_paise": 4500, "status": "PLACED"}]
    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["ORD-001"]
    assert report["amount_mismatches"] == []


def test_late_payment_on_previously_cancelled_order():
    """Payment confirmed arriving after cancellation should set refund_due_paise."""
    order = new_order("ORD-LATE", 3500, "PLACED")
    # Cancel while UNPAID
    cancelled = apply_order_event(order, ev("E1", "cancel_requested"))
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["payment_status"] == "UNPAID"
    assert cancelled["refund_due_paise"] == 0

    # Late payment arrives
    paid = apply_order_event(cancelled, ev("E2", "payment_confirmed"))
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 3500


def test_refund_processed_replay_idempotency():
    """Replaying a refund_processed event should not deduct or re-add refund amount."""
    order = new_order("ORD-REF", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    refund_event = ev("RF-1", "refund_processed", amount_paise=2000)
    step1 = apply_order_event(order, refund_event)
    assert step1["refunded_paise"] == 2000
    assert step1["payment_status"] == "PAID"
    assert step1["processed_event_ids"] == ["RF-1"]

    # Replay same refund event
    step2 = apply_order_event(step1, refund_event)
    assert step2["refunded_paise"] == 2000
    assert step2["payment_status"] == "PAID"
    assert step2["processed_event_ids"] == ["RF-1"]


def test_cumulative_partial_refunds_to_completion_and_overage_rejection():
    """Test sequential partial refunds reaching exact full refund, and rejecting further refund attempts."""
    order = new_order("ORD-MULTI", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    # First partial refund: 3000 / 5000
    s1 = apply_order_event(order, ev("R1", "refund_processed", amount_paise=3000))
    assert s1["refunded_paise"] == 3000
    assert s1["payment_status"] == "PAID"

    # Second refund exceeding remaining 2000: attempted 2500 -> must be rejected
    s2 = apply_order_event(s1, ev("R2", "refund_processed", amount_paise=2500))
    assert s2["refunded_paise"] == 3000
    assert s2["payment_status"] == "PAID"

    # Second valid partial refund: remaining 2000 -> full refund reached
    s3 = apply_order_event(s1, ev("R3", "refund_processed", amount_paise=2000))
    assert s3["refunded_paise"] == 5000
    assert s3["payment_status"] == "REFUNDED"

    # Third refund when already fully refunded: rejected
    s4 = apply_order_event(s3, ev("R4", "refund_processed", amount_paise=100))
    assert s4["refunded_paise"] == 5000
    assert s4["payment_status"] == "REFUNDED"


def test_defensive_handling_of_malformed_inputs():
    """Empty orders, missing fields, or invalid structures must not raise exceptions."""
    assert apply_order_event(None, ev("E1", "payment_confirmed")) == {}
    assert apply_order_event({}, None) == {
        "payment_status": "UNPAID",
        "refund_due_paise": 0,
        "refunded_paise": 0,
        "processed_event_ids": [],
    }
    # Event without event_id
    res = apply_order_event(new_order("O1", 1000), {"type": "payment_confirmed"})
    assert res["payment_status"] == "PAID"
    assert res["processed_event_ids"] == []

    # Reconciliation with None inputs
    empty_rep = reconcile_orders(None, None)
    assert empty_rep["matched"] == []
    assert empty_rep["missing_from_provider"] == []


def test_boolean_refund_amount_rejected():
    """Booleans (True/False) must not be treated as integer paise."""
    order = new_order("ORD-BOOL", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    out_true = apply_order_event(order, ev("R_TRUE", "refund_processed", amount_paise=True))
    assert out_true["refunded_paise"] == 0
    assert out_true["payment_status"] == "PAID"

    out_false = apply_order_event(order, ev("R_FALSE", "refund_processed", amount_paise=False))
    assert out_false["refunded_paise"] == 0
    assert out_false["payment_status"] == "PAID"


def test_summarise_orders_by_state_stretch():
    """Verify order state distribution summarisation."""
    orders = [
        {"order_id": "1", "status": "PLACED"},
        {"order_id": "2", "status": "PLACED"},
        {"order_id": "3", "status": "ACCEPTED"},
        {"order_id": "4", "status": "DELIVERED"},
        {"order_id": "5", "status": "CANCELLED"},
        {"order_id": "6"},  # missing status defaults to UNKNOWN
    ]
    summary = summarise_orders_by_state(orders)
    assert summary == {
        "ACCEPTED": 1,
        "CANCELLED": 1,
        "DELIVERED": 1,
        "PLACED": 2,
        "UNKNOWN": 1,
    }
    assert summarise_orders_by_state([]) == {}
    assert summarise_orders_by_state(None) == {}
