"""AI-assisted reference regressions; original acceptance tests remain intact."""
from copy import deepcopy
from itertools import permutations
import json
from pathlib import Path
import subprocess
import sys

import pytest

from fixtures import sample_orders, sample_provider_orders
from models import new_order
from service import apply_order_event, reconcile_orders


def event(event_id, kind, **fields):
    return {"event_id": event_id, "type": kind, **fields}


def refundable_order():
    order = new_order("O", 1000)
    for item in [event("pay", "payment_confirmed"), event("cancel", "cancel_requested")]:
        order = apply_order_event(order, item)
    return order


def test_partial_duplicate_conflicting_payload_and_completion():
    original = refundable_order()
    first = apply_order_event(original, event("r1", "refund_processed", amount_paise=400))
    assert first["payment_status"] == "PAID"
    assert first["refund_due_paise"] == 1000
    assert first["refunded_paise"] == 400
    assert apply_order_event(first, event("r1", "refund_processed", amount_paise=600)) == first
    assert apply_order_event(first, event("too-much", "refund_processed", amount_paise=601))["refunded_paise"] == 400
    full = apply_order_event(first, event("r2", "refund_processed", amount_paise=600))
    assert full["payment_status"] == "REFUNDED"
    assert full["refunded_paise"] == full["refund_due_paise"] == 1000
    assert apply_order_event(full, event("r2", "refund_processed", amount_paise=600)) == full
    after_extra = apply_order_event(full, event("r3", "refund_processed", amount_paise=1))
    assert after_extra["refunded_paise"] == 1000
    assert original["refunded_paise"] == 0


@pytest.mark.parametrize("kind", ["cancel_requested", "restaurant_rejected"])
def test_late_payment_after_unpaid_terminal_event_establishes_due(kind):
    terminal = apply_order_event(new_order("O", 1000), event("end", kind))
    assert terminal["payment_status"] == "UNPAID"
    assert terminal["refund_due_paise"] == 0
    paid = apply_order_event(terminal, event("late", "payment_confirmed"))
    assert paid["status"] == terminal["status"]
    assert paid["refund_due_paise"] == 1000
    complete = apply_order_event(paid, event("r", "refund_processed", amount_paise=1000))
    assert complete["payment_status"] == "REFUNDED"


def test_new_payment_notification_cannot_reopen_fully_refunded_order():
    complete = apply_order_event(refundable_order(), event("r", "refund_processed", amount_paise=1000))
    replay = apply_order_event(complete, event("different-payment-id", "payment_confirmed"))
    assert replay["payment_status"] == "REFUNDED"
    assert replay["refunded_paise"] == replay["refund_due_paise"] == 1000


def test_rejected_refund_is_consumed_and_cannot_become_effective_on_replay():
    premature = event("early", "refund_processed", amount_paise=1000)
    ignored = apply_order_event(new_order("O", 1000), premature)
    assert ignored["processed_event_ids"] == ["early"]
    paid = apply_order_event(ignored, event("p", "payment_confirmed"))
    cancelled = apply_order_event(paid, event("c", "cancel_requested"))
    assert apply_order_event(cancelled, premature) == cancelled
    assert cancelled["refunded_paise"] == 0


@pytest.mark.parametrize("malformed", [
    {}, None, [], "event", 1,
    {"type": "payment_confirmed"},
    {"event_id": None, "type": "payment_confirmed"},
    {"event_id": "", "type": "payment_confirmed"},
    {"event_id": "  ", "type": "payment_confirmed"},
    {"event_id": True, "type": "payment_confirmed"},
    {"event_id": [], "type": "payment_confirmed"},
    {"event_id": "x"},
    {"event_id": "x", "type": []},
    {"event_id": "x", "type": {}},
    {"event_id": "x", "type": "unknown"},
    {"event_id": "x", "type": "payment_confirmed", "order_id": "OTHER"},
    {"event_id": "x", "type": "payment_confirmed", "order_id": None},
])
def test_bad_envelope_or_unknown_order_is_an_exact_noop(malformed):
    order = new_order("O", 1000)
    before_order, before_event = deepcopy(order), deepcopy(malformed)
    result = apply_order_event(order, malformed)
    assert result == before_order
    assert result is not order
    assert order == before_order
    assert malformed == before_event


@pytest.mark.parametrize("amount", [True, False, 0, -1, 1.0, "100", None, [], {}, 1001])
def test_invalid_refund_preserves_money_and_is_idempotent(amount):
    order = refundable_order()
    item = event("bad-refund", "refund_processed", amount_paise=amount)
    once = apply_order_event(order, item)
    assert once["payment_status"] == "PAID"
    assert once["refund_due_paise"] == 1000
    assert once["refunded_paise"] == 0
    assert apply_order_event(once, item) == once


@pytest.mark.parametrize("field,value", [
    ("total_paise", -1), ("total_paise", True), ("total_paise", "1000"),
    ("refund_due_paise", 1001), ("refund_due_paise", None),
    ("refunded_paise", 1001), ("refunded_paise", -1),
    ("processed_event_ids", None), ("processed_event_ids", [None]),
    ("status", []), ("status", "UNKNOWN"), ("order_id", ""),
    ("payment_status", {}), ("payment_status", "UNKNOWN"),
])
def test_unsafe_snapshot_is_not_silently_repaired(field, value):
    order = refundable_order()
    order[field] = value
    before = deepcopy(order)
    assert apply_order_event(order, event("r", "refund_processed", amount_paise=1)) == before
    assert order == before


@pytest.mark.parametrize("missing", ["order_id", "status", "total_paise"])
def test_missing_required_order_field_is_unchanged(missing):
    order = new_order("O", 1000)
    del order[missing]
    assert apply_order_event(order, event("p", "payment_confirmed")) == order


def test_legacy_optional_fields_are_initialized_only_for_valid_event():
    legacy = {"order_id": "O", "total_paise": 1000, "status": "PLACED"}
    assert apply_order_event(legacy, {}) == legacy
    result = apply_order_event(legacy, event("p", "payment_confirmed"))
    assert result["payment_status"] == "PAID"
    assert result["processed_event_ids"] == ["p"]
    assert result["refund_due_paise"] == result["refunded_paise"] == 0


def test_returned_history_and_metadata_do_not_alias_inputs():
    order = refundable_order()
    order["metadata"] = {"tags": ["synthetic"]}
    item = event("r", "refund_processed", amount_paise=400)
    before_order, before_event = deepcopy(order), deepcopy(item)
    result = apply_order_event(order, item)
    result["metadata"]["tags"].append("new")
    result["processed_event_ids"].append("external")
    assert order == before_order
    assert item == before_event


def test_cancel_after_dispatch_does_not_create_refund_obligation():
    order = new_order("O", 1000)
    for item in [event("p", "payment_confirmed"), event("a", "restaurant_accepted"),
                 event("d", "dispatch_started"), event("c", "cancel_requested")]:
        order = apply_order_event(order, item)
    assert (order["status"], order["refund_due_paise"]) == ("OUT_FOR_DELIVERY", 0)
    assert apply_order_event(order, event("r", "refund_processed", amount_paise=1000))["refunded_paise"] == 0


def test_event_id_is_scoped_to_the_addressed_order():
    item = event("shared", "payment_confirmed")
    assert apply_order_event(new_order("A", 100), item)["payment_status"] == "PAID"
    assert apply_order_event(new_order("B", 100), item)["payment_status"] == "PAID"


def test_reconciliation_reports_both_mismatches_and_missing_sides_separately():
    left = [
        {"order_id": "C", "amount_paise": 100, "status": "PLACED"},
        {"order_id": "A", "amount_paise": 100, "status": "PLACED"},
        {"order_id": "B", "amount_paise": 100, "status": "PLACED"},
    ]
    right = [
        {"order_id": "A", "amount_paise": 90, "status": "DELIVERED"},
        {"order_id": "D", "amount_paise": 100, "status": "PLACED"},
        {"order_id": "B", "amount_paise": 100, "status": "PLACED"},
    ]
    before = deepcopy((left, right))
    expected = {
        "matched": ["B"], "missing_from_provider": ["C"],
        "missing_from_internal": ["D"], "amount_mismatches": ["A"],
        "status_mismatches": ["A"],
    }
    for left_order in permutations(left):
        for right_order in permutations(right):
            assert reconcile_orders(list(left_order), list(right_order)) == expected
    assert (left, right) == before


def test_domain_totals_and_provider_amounts_reconcile_in_real_demo():
    assert reconcile_orders(sample_orders(), sample_provider_orders()) == {
        "matched": ["ORD-101"], "missing_from_provider": ["ORD-103"],
        "missing_from_internal": ["ORD-104"], "amount_mismatches": [],
        "status_mismatches": ["ORD-102"],
    }


def test_exact_duplicate_summaries_collapse_despite_metadata_difference():
    a = {"order_id": "A", "amount_paise": 0, "status": "PLACED"}
    b = {**a, "provider_reference": "OTHER"}
    assert reconcile_orders([a, b], [b, a])["matched"] == ["A"]


@pytest.mark.parametrize("side", ["internal", "provider"])
@pytest.mark.parametrize("field,value", [("amount_paise", 101), ("status", "CANCELLED")])
def test_conflicting_duplicate_summaries_raise_independent_of_order(side, field, value):
    a = {"order_id": "A", "amount_paise": 100, "status": "PLACED"}
    b = {**a, field: value}
    for rows in ([a, b], [b, a]):
        before = deepcopy(rows)
        args = (rows, [a]) if side == "internal" else ([a], rows)
        with pytest.raises(ValueError, match="conflicting duplicate"):
            reconcile_orders(*args)
        assert rows == before


@pytest.mark.parametrize("row", [
    None, [], "row", {},
    {"order_id": None, "amount_paise": 1, "status": "PLACED"},
    {"order_id": [], "amount_paise": 1, "status": "PLACED"},
    {"order_id": "A", "status": "PLACED"},
    {"order_id": "A", "amount_paise": None, "status": "PLACED"},
    {"order_id": "A", "amount_paise": True, "status": "PLACED"},
    {"order_id": "A", "amount_paise": 1.5, "status": "PLACED"},
    {"order_id": "A", "amount_paise": -1, "status": "PLACED"},
    {"order_id": "A", "amount_paise": 1},
    {"order_id": "A", "amount_paise": 1, "status": []},
    {"order_id": "A", "amount_paise": 1, "total_paise": True, "status": "PLACED"},
    {"order_id": "A", "amount_paise": 1, "total_paise": 2, "status": "PLACED"},
])
@pytest.mark.parametrize("side", ["internal", "provider"])
def test_malformed_summary_never_becomes_false_match(row, side):
    before = deepcopy(row)
    args = ([row], []) if side == "internal" else ([], [row])
    with pytest.raises(ValueError):
        reconcile_orders(*args)
    assert row == before


@pytest.mark.parametrize("records", [None, {}, "records", 1])
def test_malformed_summary_collection_raises_clear_value_error(records):
    with pytest.raises(ValueError, match="summaries must be"):
        reconcile_orders(records, [])


def test_full_dataset_reconciles_and_every_event_replay_is_safe():
    data = json.loads((Path(__file__).resolve().parents[1] / "data/records.json").read_text())
    before = deepcopy(data)
    report = reconcile_orders(data["orders"], data["provider_records"])
    left = {row["order_id"]: row for row in data["orders"]}
    right = {row["order_id"]: row for row in data["provider_records"]}
    assert report["missing_from_provider"] == sorted(left.keys() - right.keys())
    assert report["missing_from_internal"] == sorted(right.keys() - left.keys())
    assert report["amount_mismatches"] == sorted(
        key for key in left.keys() & right.keys()
        if left[key]["total_paise"] != right[key]["amount_paise"]
    )
    assert report["status_mismatches"] == sorted(
        key for key in left.keys() & right.keys()
        if left[key]["status"] != right[key]["status"]
    )
    for item in data["events"]:
        order_id = item.get("order_id")
        if order_id not in left:
            continue  # This API applies to one known order; unknown routes are not created.
        old = left[order_id]
        result = apply_order_event(old, item)
        assert apply_order_event(result, item) == result
        assert 0 <= result["refunded_paise"] <= result["refund_due_paise"] <= result["total_paise"]
        assert result["refunded_paise"] >= old["refunded_paise"]
        if old["payment_status"] == "REFUNDED":
            assert result["payment_status"] == "REFUNDED"
        left[order_id] = result
    assert data == before


def test_original_main_runs_as_a_module():
    result = subprocess.run([sys.executable, "-m", "main"], text=True, capture_output=True, check=True,
                            cwd=Path(__file__).resolve().parents[1])
    assert "matched: ['ORD-101']" in result.stdout
    assert "status_mismatches: ['ORD-102']" in result.stdout
