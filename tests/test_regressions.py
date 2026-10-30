"""Additional regression coverage for malformed and boundary inputs."""

from models import new_order
from service import apply_order_event, reconcile_orders


def event(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_duplicate_refund_event_does_not_apply_twice():
    order = new_order("R-1", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    refund = event("refund-1", "refund_processed", amount_paise=600)

    first = apply_order_event(order, refund)
    replay = apply_order_event(first, refund)

    assert first["refunded_paise"] == 600
    assert replay["refunded_paise"] == 600
    assert replay["payment_status"] == "PAID"
    assert replay["processed_event_ids"] == ["refund-1"]


def test_same_event_id_with_different_payload_is_still_ignored():
    order = new_order("R-2", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    first = apply_order_event(
        order, event("refund-1", "refund_processed", amount_paise=400)
    )
    replay = apply_order_event(
        first, event("refund-1", "refund_processed", amount_paise=1000)
    )
    assert replay["refunded_paise"] == 400


def test_event_without_id_or_unknown_type_is_ignored():
    order = new_order("E-1", 500)
    missing_id = apply_order_event(order, {"type": "payment_confirmed"})
    unknown = apply_order_event(order, event("e-2", "unexpected_event"))
    assert missing_id == order
    assert unknown == order


def test_refund_requires_integer_paise_and_rejects_bool():
    order = new_order("R-3", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    for amount in (True, 0.5, "100", None, [], {}):
        result = apply_order_event(
            order, event(f"bad-{type(amount).__name__}", "refund_processed", amount_paise=amount)
        )
        assert result["refunded_paise"] == 0
        assert result["payment_status"] == "PAID"


def test_cumulative_refund_cannot_exceed_due():
    order = new_order("R-4", 1000, "REJECTED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    partial = apply_order_event(
        order, event("r-1", "refund_processed", amount_paise=700)
    )
    excessive = apply_order_event(
        partial, event("r-2", "refund_processed", amount_paise=301)
    )
    assert excessive["refunded_paise"] == 700
    assert excessive["payment_status"] == "PAID"


def test_full_refund_only_marks_refunded_when_due_is_reached():
    order = new_order("R-5", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    partial = apply_order_event(order, event("r-1", "refund_processed", amount_paise=999))
    full = apply_order_event(partial, event("r-2", "refund_processed", amount_paise=1))
    assert partial["payment_status"] == "PAID"
    assert full["payment_status"] == "REFUNDED"
    assert full["refunded_paise"] == 1000


def test_reconciliation_reports_both_amount_and_status_mismatches():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 90, "status": "DELIVERED"}],
    )
    assert report["amount_mismatches"] == ["A"]
    assert report["status_mismatches"] == ["A"]
    assert report["matched"] == []


def test_reconciliation_ignores_malformed_rows_and_surfaces_missing_fields():
    report = reconcile_orders(
        [None, {}, {"order_id": "A", "amount_paise": 100}],
        [{"order_id": "A"}],
    )
    assert report["amount_mismatches"] == ["A"]
    assert report["status_mismatches"] == ["A"]
    assert report["matched"] == []


def test_reconciliation_is_deterministic_for_mixed_id_types():
    rows = [
        {"order_id": "B", "amount_paise": 1, "status": "PLACED"},
        {"order_id": 2, "amount_paise": 1, "status": "PLACED"},
        {"order_id": "A", "amount_paise": 1, "status": "PLACED"},
    ]
    report = reconcile_orders(rows, rows)
    assert report["matched"] == [2, "A", "B"]


def test_late_payment_after_paid_eligible_order_was_cancelled_sets_refund_due():
    order = new_order("LATE-1", 1200, "CANCELLED")
    result = apply_order_event(order, event("payment-1", "payment_confirmed"))
    assert result["payment_status"] == "PAID"
    assert result["refund_due_paise"] == 1200


def test_malformed_event_type_and_wrong_order_id_are_ignored():
    order = new_order("SAFE-1", 750)
    malformed = apply_order_event(order, event("bad-type", [], amount_paise=700))
    wrong_order = apply_order_event(
        order,
        {"event_id": "wrong-order", "order_id": "SAFE-2", "type": "payment_confirmed"},
    )
    assert malformed == order
    assert wrong_order == order


def test_reconciliation_rejects_non_integer_amounts_even_when_values_match():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": True, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 1, "status": "PLACED"}],
    )
    assert report["amount_mismatches"] == ["A"]
    assert report["matched"] == []


def test_reconciliation_maps_internal_total_to_provider_amount():
    report = reconcile_orders(
        [{"order_id": "A", "total_paise": 45900, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 45900, "status": "PLACED"}],
    )
    assert report["matched"] == ["A"]
    assert report["amount_mismatches"] == []
