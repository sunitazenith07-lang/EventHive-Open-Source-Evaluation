"""Regression tests for the three bugs fixed in service.py."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_duplicate_event_is_not_applied_twice():
    """Replaying the same event_id must not change state a second time."""
    order = new_order("O", 1000)
    e = ev("E1", "payment_confirmed")
    first = apply_order_event(order, e)
    second = apply_order_event(first, e)
    assert second["payment_status"] == "PAID"
    assert second["processed_event_ids"] == ["E1"]


def test_refund_rejected_on_ineligible_order():
    """Refund on a PLACED order (not cancelled/rejected) must not apply."""
    order = new_order("O", 1000)
    r = apply_order_event(order, ev("R1", "refund_processed", amount_paise=500))
    assert r["refunded_paise"] == 0
    assert r["payment_status"] == "UNPAID"


def test_refund_rejected_for_negative_amount():
    """Negative refund amounts must be silently ignored."""
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    r = apply_order_event(order, ev("R1", "refund_processed", amount_paise=-100))
    assert r["refunded_paise"] == 0


def test_refund_rejected_for_boolean_amount():
    """True (==1 in Python) must not be accepted as a valid paise amount."""
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    r = apply_order_event(order, ev("R1", "refund_processed", amount_paise=True))
    assert r["refunded_paise"] == 0


def test_refund_cannot_exceed_refund_due():
    """A refund larger than the outstanding due must be rejected entirely."""
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    r = apply_order_event(order, ev("R1", "refund_processed", amount_paise=1200))
    assert r["refunded_paise"] == 0


def test_partial_then_overflow_refund():
    """After a partial refund, a second refund that would overflow must be rejected."""
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    step1 = apply_order_event(order, ev("R1", "refund_processed", amount_paise=600))
    step2 = apply_order_event(step1, ev("R2", "refund_processed", amount_paise=500))
    assert step2["refunded_paise"] == 600  # Overflow rejected
    assert step2["payment_status"] == "PAID"


def test_status_mismatch_reported_in_reconciliation():
    """Two records with same amount but different statuses must go to status_mismatches."""
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 1000, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 1000, "status": "DELIVERED"}],
    )
    assert report["status_mismatches"] == ["A"]
    assert report["matched"] == []


def test_reconciliation_dual_mismatch_not_in_matched():
    """An order with both amount and status mismatch must never appear in matched."""
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 500, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 999, "status": "CANCELLED"}],
    )
    assert report["matched"] == []
    assert report["amount_mismatches"] == ["A"]
    assert report["status_mismatches"] == ["A"]


def test_late_payment_on_rejected_order_sets_refund_due():
    """Payment arriving after restaurant rejection must set refund_due_paise."""
    order = new_order("O", 2000, "REJECTED")
    order["payment_status"] = "UNPAID"
    r = apply_order_event(order, ev("P1", "payment_confirmed"))
    assert r["payment_status"] == "PAID"
    assert r["refund_due_paise"] == 2000


def test_cancel_after_dispatch_is_ignored():
    """Cancellation on an OUT_FOR_DELIVERY order must have no effect."""
    order = new_order("O", 1000, "OUT_FOR_DELIVERY")
    order["payment_status"] = "PAID"
    r = apply_order_event(order, ev("C1", "cancel_requested"))
    assert r["status"] == "OUT_FOR_DELIVERY"
    assert r["refund_due_paise"] == 0


def test_full_refund_transitions_to_refunded_status():
    """When refunded_paise equals refund_due_paise exactly, payment_status must become REFUNDED."""
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    r = apply_order_event(order, ev("R1", "refund_processed", amount_paise=1000))
    assert r["refunded_paise"] == 1000
    assert r["payment_status"] == "REFUNDED"


def test_input_order_dict_is_not_mutated():
    """apply_order_event must never modify the original order dict passed in."""
    order = new_order("O", 1000)
    before = dict(order)
    apply_order_event(order, ev("E1", "restaurant_accepted"))
    assert order == before
