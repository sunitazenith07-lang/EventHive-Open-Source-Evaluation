"""Regression tests for previously unsafe order and refund handling."""
from models import new_order
from service import apply_order_event, reconcile_orders


def test_event_application_does_not_mutate_input():
    order = new_order("R-1", 1000)
    updated = apply_order_event(order, {"event_id": "pay-1", "type": "payment_confirmed"})
    assert order["payment_status"] == "UNPAID"
    assert updated["payment_status"] == "PAID"


def test_duplicate_partial_refund_is_idempotent():
    order = new_order("R-2", 1000)
    for event in [
        {"event_id": "pay", "type": "payment_confirmed"},
        {"event_id": "cancel", "type": "cancel_requested"},
        {"event_id": "refund", "type": "refund_processed", "amount_paise": 400},
    ]:
        order = apply_order_event(order, event)
    replayed = apply_order_event(order, {"event_id": "refund", "type": "refund_processed", "amount_paise": 400})
    assert replayed["refunded_paise"] == 400
    assert replayed["payment_status"] == "PAID"


def test_reconciliation_reports_both_amount_and_status_difference():
    report = reconcile_orders(
        [{"order_id": "R-3", "amount_paise": 100, "status": "CANCELLED"}],
        [{"order_id": "R-3", "amount_paise": 90, "status": "REFUNDED"}],
    )
    assert report["amount_mismatches"] == ["R-3"]
    assert report["status_mismatches"] == ["R-3"]
    assert report["matched"] == []
