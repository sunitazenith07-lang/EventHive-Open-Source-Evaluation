from copy import deepcopy

import pytest

from models import new_order
from service import apply_order_event, reconcile_orders


def event(eid, kind, **extra):
    return dict(event_id=eid, type=kind, **extra)


def test_refund_sequence_and_replay():
    order = new_order("O", 1000)
    steps = [
        (event("p", "payment_confirmed"), ("PLACED", "PAID", 0, 0)),
        (event("c", "cancel_requested"), ("CANCELLED", "PAID", 1000, 0)),
        (event("r1", "refund_processed", amount_paise=400), ("CANCELLED", "PAID", 1000, 400)),
        (event("r1", "refund_processed", amount_paise=400), ("CANCELLED", "PAID", 1000, 400)),
        (event("r2", "refund_processed", amount_paise=600), ("CANCELLED", "REFUNDED", 1000, 1000)),
        (event("p2", "payment_confirmed"), ("CANCELLED", "REFUNDED", 1000, 1000)),
    ]
    for e, expected in steps:
        previous = deepcopy(order)
        updated = apply_order_event(order, e)
        assert order == previous
        assert tuple(updated[k] for k in ("status", "payment_status", "refund_due_paise", "refunded_paise")) == expected
        order = updated
    assert order["processed_event_ids"] == ["p", "c", "r1", "r2", "p2"]


@pytest.mark.parametrize("status", ["CANCELLED", "REJECTED"])
def test_late_payment_creates_refund_due(status):
    order = apply_order_event(new_order("O", 1000, status), event("p", "payment_confirmed"))
    assert order["refund_due_paise"] == 1000
    assert order["payment_status"] == "PAID"


@pytest.mark.parametrize("bad", [None, [], {}, {"type": "payment_confirmed"},
    event(None, "payment_confirmed"), event([], "payment_confirmed"),
    event("", "payment_confirmed"), event("x", []), event("x", "unknown"),
    event("x", "payment_confirmed", order_id="UNKNOWN"), event("x", "refund_processed")])
def test_malformed_or_misrouted_event_is_noop(bad):
    order = new_order("O", 1000)
    assert apply_order_event(order, bad) == order


def test_duplicate_id_with_changed_payload_is_ignored():
    order = apply_order_event(new_order("O", 1000), event("x", "payment_confirmed"))
    assert apply_order_event(order, event("x", "cancel_requested")) == order


@pytest.mark.parametrize("field,value", [("total_paise", True), ("refunded_paise", -1),
    ("refund_due_paise", 2000), ("processed_event_ids", None)])
def test_corrupt_order_is_not_modified(field, value):
    order = new_order("O", 1000)
    order[field] = value
    assert apply_order_event(order, event("x", "payment_confirmed")) == order


def test_reconciliation_reports_both_differences_and_normalizes_total():
    report = reconcile_orders(
        [new_order("A", 100), new_order("B", 200)],
        [dict(order_id="B", amount_paise=201, status="DELIVERED"),
         dict(order_id="A", amount_paise=100, status="PLACED")])
    assert report["matched"] == ["A"]
    assert report["amount_mismatches"] == report["status_mismatches"] == ["B"]


def test_reconciliation_missing_fields_and_identical_duplicates():
    row = dict(order_id="A")
    report = reconcile_orders([None, {}, row, row], [row])
    assert report["matched"] == []
    assert report["amount_mismatches"] == report["status_mismatches"] == ["A"]


def test_conflicting_duplicate_records_rejected_in_either_order():
    rows = [dict(order_id="A", amount_paise=1), dict(order_id="A", amount_paise=2)]
    for ordered in (rows, rows[::-1]):
        with pytest.raises(ValueError, match="Conflicting records"):
            reconcile_orders(ordered, [])

def test_synthetic_dataset_preserves_state_invariants():
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).parents[1] / "data" / "records.json").read_text())
    orders = {row["order_id"]: deepcopy(row) for row in data["orders"]}
    for e in data["events"]:
        oid = e.get("order_id")
        if oid not in orders:
            continue  # Routing belongs to the caller; never create an unknown order.
        original = deepcopy(orders[oid])
        updated = apply_order_event(orders[oid], e)
        assert orders[oid] == original
        assert 0 <= updated["refunded_paise"] <= updated["refund_due_paise"] <= updated["total_paise"]
        assert apply_order_event(updated, e) == updated
        orders[oid] = updated
    report = reconcile_orders(data["orders"], data["provider_records"])
    assert report == reconcile_orders(data["orders"][::-1], data["provider_records"][::-1])
    assert all(ids == sorted(ids) for ids in report.values())
