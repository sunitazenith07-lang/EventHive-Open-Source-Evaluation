from models import new_order
from service import apply_order_event, reconcile_orders


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_regression_duplicate_refund_event_is_idempotent():
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    first = apply_order_event(order, ev("r1", "refund_processed", amount_paise=400))
    second = apply_order_event(first, ev("r1", "refund_processed", amount_paise=400))
    assert second["refunded_paise"] == 400
    assert second["processed_event_ids"] == ["r1"]


def test_regression_refund_ignored_for_ineligible_order():
    order = new_order("O", 1000, "PLACED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    result = apply_order_event(order, ev("r1", "refund_processed", amount_paise=1000))
    assert result["refunded_paise"] == 0
    assert result["payment_status"] == "PAID"


def test_regression_refund_rejects_bool_amount():
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    result = apply_order_event(order, ev("r1", "refund_processed", amount_paise=True))
    assert result["refunded_paise"] == 0


def test_regression_refund_cannot_exceed_outstanding_due():
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    first = apply_order_event(order, ev("r1", "refund_processed", amount_paise=600))
    second = apply_order_event(first, ev("r2", "refund_processed", amount_paise=500))
    assert second["refunded_paise"] == 600
    assert second["payment_status"] == "PAID"


def test_regression_partial_refunds_accumulate_to_refunded():
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    first = apply_order_event(order, ev("r1", "refund_processed", amount_paise=300))
    second = apply_order_event(first, ev("r2", "refund_processed", amount_paise=700))
    assert second["refunded_paise"] == 1000
    assert second["payment_status"] == "REFUNDED"


def test_regression_cancel_after_dispatch_is_ignored():
    order = new_order("O", 1000, "OUT_FOR_DELIVERY")
    result = apply_order_event(order, ev("c1", "cancel_requested"))
    assert result["status"] == "OUT_FOR_DELIVERY"


def test_regression_payment_after_rejection_sets_refund_due():
    order = new_order("O", 1000, "REJECTED")
    result = apply_order_event(order, ev("p1", "payment_confirmed"))
    assert result["payment_status"] == "PAID"
    assert result["refund_due_paise"] == 1000


def test_regression_reconciliation_status_mismatch():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 100, "status": "DELIVERED"}],
    )
    assert report["status_mismatches"] == ["A"]
    assert report["matched"] == []


def test_regression_reconciliation_combined_mismatch_both_categories():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 90, "status": "DELIVERED"}],
    )
    assert report["amount_mismatches"] == ["A"]
    assert report["status_mismatches"] == ["A"]
    assert report["matched"] == []


def test_regression_reconciliation_maps_total_to_amount():
    report = reconcile_orders(
        [{"order_id": "A", "total_paise": 100, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
    )
    assert report["matched"] == ["A"]
    assert report["amount_mismatches"] == []


def test_regression_reconciliation_empty_and_malformed_safe():
    report = reconcile_orders([], ["bad", {"order_id": "B", "amount_paise": 1, "status": "PLACED"}])
    assert report["missing_from_internal"] == ["B"]
    assert all(isinstance(v, list) for v in report.values())


def test_regression_input_order_not_mutated():
    order = new_order("O", 1000)
    before = dict(order)
    apply_order_event(order, ev("e1", "payment_confirmed"))
    assert order == before


def test_regression_unknown_event_does_not_mutate():
    order = new_order("O", 1000)
    result = apply_order_event(order, ev("e1", "mystery_event"))
    assert result["status"] == "PLACED"
    assert result["refunded_paise"] == 0


def test_regression_conflicting_replay_is_ignored():
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    first = apply_order_event(order, ev("r1", "refund_processed", amount_paise=400))
    # Same event id but different payload must not apply a second time.
    second = apply_order_event(first, ev("r1", "refund_processed", amount_paise=1000))
    assert second["refunded_paise"] == 400
