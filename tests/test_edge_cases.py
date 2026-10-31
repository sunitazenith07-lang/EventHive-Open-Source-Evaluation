from models import new_order
from service import apply_order_event, reconcile_orders


def event(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_two_partial_refunds_mark_refunded_only_at_full_due():
    order = new_order("EDGE-1", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)

    partial = apply_order_event(
        order, event("refund-1", "refund_processed", amount_paise=300)
    )
    complete = apply_order_event(
        partial, event("refund-2", "refund_processed", amount_paise=700)
    )

    assert partial["refunded_paise"] == 300
    assert partial["payment_status"] == "PAID"
    assert complete["refunded_paise"] == 1000
    assert complete["payment_status"] == "REFUNDED"


def test_refund_cannot_exceed_remaining_due_after_partial_refund():
    order = new_order("EDGE-2", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    partial = apply_order_event(
        order, event("refund-1", "refund_processed", amount_paise=800)
    )

    result = apply_order_event(
        partial, event("refund-2", "refund_processed", amount_paise=201)
    )

    assert result["refunded_paise"] == 800
    assert result["payment_status"] == "PAID"


def test_boolean_is_not_accepted_as_refund_amount():
    order = new_order("EDGE-3", 1000, "REJECTED")
    order.update(payment_status="PAID", refund_due_paise=1000)

    result = apply_order_event(
        order, event("refund-1", "refund_processed", amount_paise=True)
    )

    assert result["refunded_paise"] == 0
    assert result["payment_status"] == "PAID"


def test_empty_event_id_does_not_change_or_record_event():
    order = new_order("EDGE-4", 1000)

    result = apply_order_event(
        order, event("", "payment_confirmed")
    )

    assert result == order


def test_reconciliation_reports_amount_and_status_mismatches_together():
    report = reconcile_orders(
        [{"order_id": "EDGE-5", "amount_paise": 1000, "status": "CANCELLED"}],
        [{"order_id": "EDGE-5", "amount_paise": 900, "status": "DELIVERED"}],
    )

    assert report["amount_mismatches"] == ["EDGE-5"]
    assert report["status_mismatches"] == ["EDGE-5"]
    assert report["matched"] == []
