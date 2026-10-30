"""Regression tests for defects fixed in service.py (added on top of the starter tests)."""
import json
from pathlib import Path

import pytest

from models import new_order
from service import (APPLIED, DUPLICATE, apply_order_event, evaluate_order_event,
                     process_events, reconcile_orders)

DATA = Path(__file__).resolve().parent.parent / "data" / "records.json"


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def paid_cancelled(total=1000):
    order = new_order("O1", total, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=total)
    return order


# --- idempotency -------------------------------------------------------------

def test_replayed_refund_is_counted_once():
    once = apply_order_event(paid_cancelled(), ev("r1", "refund_processed", amount_paise=400))
    twice, outcome = evaluate_order_event(once, ev("r1", "refund_processed", amount_paise=400))
    assert outcome == DUPLICATE
    assert twice["refunded_paise"] == 400
    assert twice["processed_event_ids"] == ["r1"]


def test_replay_with_conflicting_payload_is_still_ignored():
    once = apply_order_event(paid_cancelled(), ev("r1", "refund_processed", amount_paise=400))
    twice, outcome = evaluate_order_event(once, ev("r1", "refund_processed", amount_paise=600))
    assert outcome == DUPLICATE
    assert twice["refunded_paise"] == 400


@pytest.mark.parametrize("event_id", [None, "", 7, ["x"]])
def test_event_without_usable_id_changes_nothing(event_id):
    order = new_order("O1", 1000)
    out, outcome = evaluate_order_event(order, {"event_id": event_id, "type": "payment_confirmed"})
    assert outcome == "missing_event_id"
    assert out["payment_status"] == "UNPAID"
    assert out["processed_event_ids"] == []


def test_rejected_refund_is_not_recorded_so_a_redelivery_can_apply_later():
    order = new_order("O1", 1000)
    order["payment_status"] = "PAID"
    early, outcome = evaluate_order_event(order, ev("r1", "refund_processed", amount_paise=1000))
    assert outcome == "refund_not_eligible"
    assert early["processed_event_ids"] == []
    cancelled = apply_order_event(early, ev("c1", "cancel_requested"))
    refunded = apply_order_event(cancelled, ev("r1", "refund_processed", amount_paise=1000))
    assert refunded["refunded_paise"] == 1000
    assert refunded["payment_status"] == "REFUNDED"


# --- transitions and malformed input ----------------------------------------

def test_cancel_after_dispatch_reports_invalid_transition():
    order = new_order("O1", 1000, "OUT_FOR_DELIVERY")
    order["payment_status"] = "PAID"
    out, outcome = evaluate_order_event(order, ev("c1", "cancel_requested"))
    assert outcome == "invalid_transition"
    assert out["status"] == "OUT_FOR_DELIVERY"
    assert out["refund_due_paise"] == 0


@pytest.mark.parametrize("event", [None, "payment_confirmed", 42, ["e1"]])
def test_non_dict_event_does_not_crash(event):
    out, outcome = evaluate_order_event(new_order("O1", 1000), event)
    assert outcome == "malformed_event"
    assert out["status"] == "PLACED"


def test_unhashable_event_type_does_not_crash():
    out, outcome = evaluate_order_event(new_order("O1", 1000), ev("e1", ["refund_processed"]))
    assert outcome == "unknown_event_type"


def test_event_for_a_different_order_is_rejected():
    out, outcome = evaluate_order_event(new_order("O1", 1000),
                                        ev("e1", "restaurant_accepted", order_id="O2"))
    assert outcome == "order_id_mismatch"
    assert out["status"] == "PLACED"


def test_unpaid_rejection_has_no_refund_due():
    out = apply_order_event(new_order("O1", 1000), ev("e1", "restaurant_rejected"))
    assert out["status"] == "REJECTED"
    assert out["refund_due_paise"] == 0


def test_payment_arriving_after_cancellation_creates_refund_due():
    order = apply_order_event(new_order("O1", 1000), ev("c1", "cancel_requested"))
    order = apply_order_event(order, ev("p1", "payment_confirmed"))
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 1000


def test_second_payment_event_with_new_id_does_not_reset_refund_state():
    order = apply_order_event(paid_cancelled(), ev("r1", "refund_processed", amount_paise=1000))
    out, outcome = evaluate_order_event(order, ev("p2", "payment_confirmed"))
    assert outcome == "already_paid"
    assert out["payment_status"] == "REFUNDED"


# --- refund safety -----------------------------------------------------------

def test_partial_then_final_refund_completes_and_further_refunds_are_rejected():
    order = apply_order_event(paid_cancelled(), ev("r1", "refund_processed", amount_paise=300))
    assert order["payment_status"] == "PAID"
    order = apply_order_event(order, ev("r2", "refund_processed", amount_paise=700))
    assert (order["refunded_paise"], order["payment_status"]) == (1000, "REFUNDED")
    out, outcome = evaluate_order_event(order, ev("r3", "refund_processed", amount_paise=1))
    assert outcome == "refund_not_eligible"
    assert out["refunded_paise"] == 1000


def test_refund_rejected_when_order_has_no_valid_total():
    order = {"order_id": "O1", "status": "PLACED", "payment_status": "PAID"}
    order = apply_order_event(order, ev("c1", "cancel_requested"))
    assert order["refund_due_paise"] == 0
    _, outcome = evaluate_order_event(order, ev("r1", "refund_processed", amount_paise=100))
    assert outcome == "refund_not_eligible"


# --- batch processing --------------------------------------------------------

def test_process_events_handles_empty_input():
    assert process_events([], []) == ({}, [])
    assert process_events(None, None) == ({}, [])


def test_process_events_reports_unknown_missing_and_duplicate_events():
    orders = [new_order("O1", 1000)]
    events = [ev("p1", "payment_confirmed", order_id="O1"),
              ev("p1", "payment_confirmed", order_id="O1"),
              ev("x1", "payment_confirmed", order_id="NOPE"),
              ev("x2", "refund_processed", amount_paise=10),
              "garbage"]
    state, rejected = process_events(orders, events)
    assert state["O1"]["payment_status"] == "PAID"
    assert [(r["index"], r["reason"]) for r in rejected] == [
        (1, DUPLICATE), (2, "unknown_order_id"), (3, "missing_order_id"), (4, "malformed_event")]


def test_process_events_does_not_mutate_inputs():
    orders = [new_order("O1", 1000)]
    events = [ev("p1", "payment_confirmed", order_id="O1")]
    snapshot = json.dumps([orders, events])
    process_events(orders, events)
    assert json.dumps([orders, events]) == snapshot


def test_dataset_replay_of_applied_events_is_idempotent_and_refunds_stay_in_bounds():
    data = json.loads(DATA.read_text())
    once, rejected_once = process_events(data["orders"], data["events"])
    rejected_index = {r["index"] for r in rejected_once}
    applied = [e for i, e in enumerate(data["events"]) if i not in rejected_index]
    # Replaying every event that was applied must change nothing at all.
    replayed, rejected_replay = process_events(list(once.values()), applied)
    assert replayed == once
    assert {r["reason"] for r in rejected_replay} == {DUPLICATE}
    # A full second pass may still apply events that arrived too early the
    # first time (e.g. ORD-1007's refund before its rejection), but a third
    # pass must then be a no-op.
    twice, _ = process_events(list(once.values()), data["events"])
    thrice, _ = process_events(list(twice.values()), data["events"])
    assert thrice == twice
    for order in list(once.values()) + list(twice.values()):
        assert isinstance(order["refunded_paise"], int)
        assert 0 <= order["refunded_paise"] <= order["refund_due_paise"]
    reasons = {r["reason"] for r in rejected_once}
    # The dataset's duplicate pairs all target orders where the first copy is
    # itself invalid, so both copies report that underlying reason; duplicates
    # of applied events are covered by the replay assertion above.
    assert {"missing_event_id", "missing_order_id", "invalid_transition",
            "unknown_event_type", "invalid_refund_amount", "refund_not_eligible"} <= reasons


# --- reconciliation ----------------------------------------------------------

def test_reconcile_reads_total_paise_from_internal_orders():
    report = reconcile_orders([new_order("A", 45900)],
                              [{"order_id": "A", "amount_paise": 45900, "status": "PLACED"}])
    assert report["matched"] == ["A"]
    assert report["amount_mismatches"] == []


def test_amount_and_status_mismatch_are_both_reported():
    report = reconcile_orders([{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
                              [{"order_id": "A", "amount_paise": 90, "status": "CANCELLED"}])
    assert report["amount_mismatches"] == ["A"]
    assert report["status_mismatches"] == ["A"]
    assert report["matched"] == []


def test_payment_status_mismatch_is_reported_separately():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 100, "status": "CANCELLED", "payment_status": "PAID"}],
        [{"order_id": "A", "amount_paise": 100, "status": "CANCELLED", "payment_status": "REFUNDED"}])
    assert report["payment_status_mismatches"] == ["A"]
    assert report["status_mismatches"] == []
    assert report["matched"] == []


def test_malformed_and_duplicate_records_are_reported_not_crashed_on():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 1, "status": "PLACED"}, {"amount_paise": 5}, None],
        [{"order_id": "A", "amount_paise": 1, "status": "PLACED"},
         {"order_id": "A", "amount_paise": 2, "status": "PLACED"}])
    assert report["matched"] == ["A"]
    assert report["invalid_records"] == ["internal[1]: missing order_id",
                                         "internal[2]: missing order_id",
                                         "provider[1]: duplicate order_id A"]


def test_reconciliation_report_is_independent_of_input_order():
    internal = [{"order_id": f"O{i}", "amount_paise": i, "status": "PLACED"} for i in range(6)]
    provider = [{"order_id": f"O{i}", "amount_paise": i + (i % 2), "status": "PLACED"}
                for i in range(1, 8)]
    assert reconcile_orders(internal, provider) == reconcile_orders(internal[::-1], provider[::-1])


def test_dataset_reconciliation_is_internally_consistent():
    data = json.loads(DATA.read_text())
    report = reconcile_orders(data["orders"], data["provider_records"])
    internal = {o["order_id"] for o in data["orders"]}
    provider = {p["order_id"] for p in data["provider_records"]}
    assert report["missing_from_provider"] == sorted(internal - provider)
    assert report["missing_from_internal"] == sorted(provider - internal)
    assert set(report["matched"]).isdisjoint(
        report["amount_mismatches"] + report["status_mismatches"]
        + report["payment_status_mismatches"])
