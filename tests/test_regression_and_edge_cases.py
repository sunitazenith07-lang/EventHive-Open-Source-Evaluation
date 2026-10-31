"""Regression and edge case tests for OrderOps."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders, summarize_orders_by_state


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_duplicate_cancellation_event_is_idempotent():
    order = new_order("ORD-1", 2500, "ACCEPTED")
    order["payment_status"] = "PAID"
    event = ev("EV-CANCEL-1", "cancel_requested")
    
    first = apply_order_event(order, event)
    assert first["status"] == "CANCELLED"
    assert first["refund_due_paise"] == 2500
    assert first["processed_event_ids"] == ["EV-CANCEL-1"]

    second = apply_order_event(first, event)
    assert second["status"] == "CANCELLED"
    assert second["refund_due_paise"] == 2500
    assert second["processed_event_ids"] == ["EV-CANCEL-1"]


def test_late_payment_confirmed_on_rejected_order_sets_refund_due():
    # Order was placed, then rejected while UNPAID
    order = new_order("ORD-2", 3000, "PLACED")
    rejected = apply_order_event(order, ev("EV-REJ-1", "restaurant_rejected"))
    assert rejected["status"] == "REJECTED"
    assert rejected["payment_status"] == "UNPAID"
    assert rejected["refund_due_paise"] == 0

    # Payment arrives late after rejection
    paid = apply_order_event(rejected, ev("EV-PAY-1", "payment_confirmed"))
    assert paid["status"] == "REJECTED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 3000


def test_late_payment_confirmed_on_cancelled_order_sets_refund_due():
    # Order was cancelled while UNPAID
    order = new_order("ORD-3", 1500, "PLACED")
    cancelled = apply_order_event(order, ev("EV-CANC-1", "cancel_requested"))
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["payment_status"] == "UNPAID"
    assert cancelled["refund_due_paise"] == 0

    # Payment confirmed arrives late
    paid = apply_order_event(cancelled, ev("EV-PAY-2", "payment_confirmed"))
    assert paid["status"] == "CANCELLED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 1500


def test_cancel_after_delivery_is_rejected():
    order = new_order("ORD-4", 4000, "DELIVERED")
    order["payment_status"] = "PAID"
    result = apply_order_event(order, ev("EV-CANC-POST", "cancel_requested"))
    assert result["status"] == "DELIVERED"
    assert result["refund_due_paise"] == 0


def test_refund_exceeding_remaining_due_is_rejected():
    order = new_order("ORD-5", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000, refunded_paise=3000)
    
    # Remaining due is 2000; attempting 2001 paise must fail
    res = apply_order_event(order, ev("EV-REF-OVER", "refund_processed", amount_paise=2001))
    assert res["refunded_paise"] == 3000
    assert res["payment_status"] == "PAID"

    # Exact remaining 2000 paise succeeds and completes refund
    res2 = apply_order_event(order, ev("EV-REF-EXACT", "refund_processed", amount_paise=2000))
    assert res2["refunded_paise"] == 5000
    assert res2["payment_status"] == "REFUNDED"


def test_boolean_refund_amounts_are_rejected():
    order = new_order("ORD-6", 2000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=2000)
    
    # Python bool inherits from int: True (1) and False (0) must be rejected
    res_true = apply_order_event(order, ev("EV-BOOL-T", "refund_processed", amount_paise=True))
    assert res_true["refunded_paise"] == 0
    assert res_true["payment_status"] == "PAID"

    res_false = apply_order_event(order, ev("EV-BOOL-F", "refund_processed", amount_paise=False))
    assert res_false["refunded_paise"] == 0


def test_malformed_inputs_handled_safely():
    # Non-dict inputs
    assert apply_order_event(None, ev("E1", "payment_confirmed")) == {}
    assert apply_order_event("not a dict", ev("E1", "payment_confirmed")) == {}
    
    order = new_order("ORD-7", 1000)
    assert apply_order_event(order, None) == order
    assert apply_order_event(order, "invalid event") == order

    # Event missing event_id
    event_no_id = {"type": "payment_confirmed"}
    res = apply_order_event(order, event_no_id)
    assert res["payment_status"] == "PAID"
    assert res["processed_event_ids"] == []


def test_reconciliation_simultaneous_amount_and_status_mismatch():
    internal = [{"order_id": "ORD-10", "total_paise": 2000, "status": "DELIVERED"}]
    provider = [{"order_id": "ORD-10", "amount_paise": 1500, "status": "PLACED"}]
    
    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-10"]
    assert report["status_mismatches"] == ["ORD-10"]
    assert report["matched"] == []
    assert report["missing_from_provider"] == []
    assert report["missing_from_internal"] == []


def test_reconciliation_handles_malformed_records():
    internal = [None, {"status": "PLACED"}, {"order_id": "ORD-11", "amount_paise": 500, "status": "PLACED"}]
    provider = [{"order_id": "ORD-11", "amount_paise": 500, "status": "PLACED"}, "invalid"]
    
    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["ORD-11"]


def test_summarize_orders_by_state():
    orders = [
        {"order_id": "1", "status": "PLACED"},
        {"order_id": "2", "status": "PLACED"},
        {"order_id": "3", "status": "ACCEPTED"},
        {"order_id": "4", "status": "CANCELLED"},
        {"order_id": "5", "status": "DELIVERED"},
        {"invalid": "entry"},
    ]
    summary = summarize_orders_by_state(orders)
    assert summary == {
        "ACCEPTED": 1,
        "CANCELLED": 1,
        "DELIVERED": 1,
        "PLACED": 2,
        "UNKNOWN": 1,
    }
    assert summarize_orders_by_state([]) == {}

