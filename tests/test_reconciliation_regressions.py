"""Reconciliation regressions using the demo, dataset and malformed summaries."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from fixtures import sample_orders, sample_provider_orders
from service import reconcile_orders


def summary(order_id="O", amount_paise=100, status="PLACED"):
    return {"order_id": order_id, "amount_paise": amount_paise, "status": status}


def test_demo_reconciles_internal_totals_and_provider_amounts():
    assert reconcile_orders(sample_orders(), sample_provider_orders()) == {
        "matched": ["ORD-101"],
        "missing_from_provider": ["ORD-103"],
        "missing_from_internal": ["ORD-104"],
        "amount_mismatches": [],
        "status_mismatches": ["ORD-102"],
    }


def test_dataset_reconciliation_preserves_both_mismatch_categories():
    path = Path(__file__).resolve().parents[1] / "data" / "records.json"
    data = json.loads(path.read_text())
    report = reconcile_orders(data["orders"], data["provider_records"])
    assert {name: len(ids) for name, ids in report.items()} == {
        "matched": 107,
        "missing_from_provider": 12,
        "missing_from_internal": 25,
        "amount_mismatches": 20,
        "status_mismatches": 12,
    }
    assert "ORD-1078" in report["amount_mismatches"]
    assert "ORD-1078" in report["status_mismatches"]
    assert all(ids == sorted(ids) for ids in report.values())
    assert report == reconcile_orders(
        list(reversed(data["orders"])), list(reversed(data["provider_records"]))
    )


def test_amount_and_status_mismatches_are_independent():
    report = reconcile_orders([summary()], [summary(amount_paise=90, status="DELIVERED")])
    assert report["amount_mismatches"] == ["O"]
    assert report["status_mismatches"] == ["O"]
    assert report["matched"] == []


def test_internal_explicit_amount_takes_precedence_over_total():
    internal = {**summary(), "total_paise": 900}
    assert reconcile_orders([internal], [summary()])["matched"] == ["O"]
    internal["amount_paise"] = None
    report = reconcile_orders([internal], [summary(amount_paise=900)])
    assert report["matched"] == []
    assert report["amount_mismatches"] == ["O"]


def test_provider_total_does_not_substitute_for_missing_amount():
    provider = {"order_id": "O", "total_paise": 100, "status": "PLACED"}
    report = reconcile_orders([summary()], [provider])
    assert report["amount_mismatches"] == ["O"]
    assert report["matched"] == []


@pytest.mark.parametrize("amount", [None, True, False, 1.0, "100", -1, [], {}])
def test_invalid_amounts_cannot_match_even_when_both_sides_agree(amount):
    row = summary(amount_paise=amount)
    report = reconcile_orders([row], [row])
    assert report["amount_mismatches"] == ["O"]
    assert report["status_mismatches"] == []
    assert report["matched"] == []


def test_zero_paise_is_a_valid_reconciliation_amount():
    assert reconcile_orders([summary(amount_paise=0)], [summary(amount_paise=0)])["matched"] == ["O"]


@pytest.mark.parametrize("status", [None, "", "   ", 1, True, [], {}])
def test_invalid_statuses_cannot_match_even_when_both_sides_agree(status):
    row = summary(status=status)
    report = reconcile_orders([row], [row])
    assert report["status_mismatches"] == ["O"]
    assert report["amount_mismatches"] == []
    assert report["matched"] == []


def test_missing_comparison_fields_report_both_mismatches():
    report = reconcile_orders([{"order_id": "O"}], [{"order_id": "O"}])
    assert report["amount_mismatches"] == ["O"]
    assert report["status_mismatches"] == ["O"]
    assert report["matched"] == []


def test_unidentifiable_rows_are_ignored_without_hiding_valid_missing_orders():
    malformed = [None, 5, "row", [], {}, {"order_id": None}, {"order_id": ""},
                 {"order_id": "   "}, {"order_id": []}, {"order_id": True}]
    report = reconcile_orders(malformed + [summary("B")], malformed + [summary("A")])
    assert report == {
        "matched": [],
        "missing_from_provider": ["B"],
        "missing_from_internal": ["A"],
        "amount_mismatches": [],
        "status_mismatches": [],
    }


def test_none_inputs_behave_as_empty_summaries():
    assert all(ids == [] for ids in reconcile_orders(None, None).values())
    assert reconcile_orders(None, [summary()])["missing_from_internal"] == ["O"]
    assert reconcile_orders([summary()], None)["missing_from_provider"] == ["O"]


def test_identical_normalized_duplicates_collapse_without_input_mutation():
    internal = [summary(), {**summary(), "extra": ["metadata"]}]
    provider = [summary(), {**summary(), "provider_reference": "another-reference"}]
    before = deepcopy((internal, provider))
    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["O"]
    assert (internal, provider) == before


@pytest.mark.parametrize("field,value,category", [
    ("amount_paise", 200, "amount_mismatches"),
    ("status", "CANCELLED", "status_mismatches"),
])
def test_conflicting_duplicates_report_the_affected_field(field, value, category):
    duplicate = {**summary(), field: value}
    for internal, provider in [
        ([summary(), duplicate], [summary()]),
        ([summary()], [summary(), duplicate]),
        ([summary(), duplicate], [summary(), duplicate]),
    ]:
        report = reconcile_orders(internal, provider)
        assert report[category] == ["O"]
        assert report["matched"] == []
        other = "status_mismatches" if category == "amount_mismatches" else "amount_mismatches"
        assert report[other] == []
        assert report == reconcile_orders(list(reversed(internal)), list(reversed(provider)))


def test_duplicate_invalid_row_cannot_be_overwritten_by_a_valid_row():
    invalid = summary(amount_paise=None, status="")
    report = reconcile_orders([invalid, summary()], [summary()])
    assert report["amount_mismatches"] == ["O"]
    assert report["status_mismatches"] == ["O"]
    assert report["matched"] == []
    assert report == reconcile_orders([summary(), invalid], [summary()])
