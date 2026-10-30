"""Regressions for event envelopes, replay safety and refund accounting."""

from copy import deepcopy

import pytest

from models import new_order
from service import apply_order_event


def event(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def paid_cancelled_order():
    order = new_order("O", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    return order


def test_replayed_partial_refund_does_not_pay_twice():
    notification = event("refund-1", "refund_processed", amount_paise=400)
    once = apply_order_event(paid_cancelled_order(), notification)

    assert apply_order_event(once, notification) == once
    assert once["refunded_paise"] == 400
    assert once["processed_event_ids"] == ["refund-1"]


def test_conflicting_payload_cannot_reuse_a_processed_id():
    paid = apply_order_event(new_order("O", 1000), event("same-id", "payment_confirmed"))
    conflicting = event("same-id", "cancel_requested")

    assert apply_order_event(paid, conflicting) == paid


def test_rejected_transition_is_recorded_and_cannot_apply_on_later_replay():
    dispatch = event("early-dispatch", "dispatch_started")
    early = apply_order_event(new_order("O", 1000), dispatch)
    assert early["status"] == "PLACED"
    assert early["processed_event_ids"] == ["early-dispatch"]

    accepted = apply_order_event(early, event("accept", "restaurant_accepted"))
    assert apply_order_event(accepted, dispatch) == accepted
    assert accepted["status"] == "ACCEPTED"


def test_ineligible_refund_cannot_be_replayed_after_cancellation():
    paid = apply_order_event(new_order("O", 1000), event("pay", "payment_confirmed"))
    refund = event("early-refund", "refund_processed", amount_paise=1000)
    early = apply_order_event(paid, refund)
    cancelled = apply_order_event(early, event("cancel", "cancel_requested"))

    assert apply_order_event(cancelled, refund) == cancelled
    assert cancelled["refund_due_paise"] == 1000
    assert cancelled["refunded_paise"] == 0


@pytest.mark.parametrize("notification", [None, [], "payment_confirmed", 1, True, {}])
def test_malformed_event_container_leaves_order_unchanged(notification):
    order = new_order("O", 1000)
    assert apply_order_event(order, notification) == order


@pytest.mark.parametrize("event_id", [None, "", 1, True, [], {}])
def test_invalid_event_id_does_not_change_state_or_history(event_id):
    order = new_order("O", 1000)
    assert apply_order_event(order, event(event_id, "payment_confirmed")) == order


def test_missing_event_id_does_not_change_state_or_history():
    order = new_order("O", 1000)
    assert apply_order_event(order, {"type": "payment_confirmed"}) == order


@pytest.mark.parametrize("kind", [None, "", "unexpected_event", 1, True, [], {}])
def test_invalid_event_type_does_not_change_state_or_history(kind):
    order = new_order("O", 1000)
    assert apply_order_event(order, event("event-1", kind)) == order


def test_missing_event_type_does_not_change_state_or_history():
    order = new_order("O", 1000)
    assert apply_order_event(order, {"event_id": "event-1"}) == order


@pytest.mark.parametrize("target", ["ANOTHER-ORDER", "", None, 1, True, [], {}])
def test_wrong_or_invalid_target_cannot_change_order(target):
    order = new_order("O", 1000)
    notification = event("payment-1", "payment_confirmed", order_id=target)

    assert apply_order_event(order, notification) == order


def test_explicit_matching_target_is_accepted():
    notification = event("payment-1", "payment_confirmed", order_id="O")
    updated = apply_order_event(new_order("O", 1000), notification)

    assert updated["payment_status"] == "PAID"
    assert updated["processed_event_ids"] == ["payment-1"]


def test_returned_copy_does_not_alias_nested_input_or_event():
    order = new_order("O", 1000)
    order["metadata"] = {"labels": ["synthetic"]}
    notification = event("payment-1", "payment_confirmed", details={"source": ["offline"]})
    before_order, before_event = deepcopy(order), deepcopy(notification)

    updated = apply_order_event(order, notification)
    updated["metadata"]["labels"].append("changed")
    updated["processed_event_ids"].append("another-id")

    assert order == before_order
    assert notification == before_event


def test_ignored_event_also_returns_an_independent_copy():
    order = new_order("O", 1000)
    order["metadata"] = {"labels": []}
    ignored = apply_order_event(order, {"type": "payment_confirmed"})
    ignored["metadata"]["labels"].append("changed")

    assert ignored is not order
    assert order["metadata"]["labels"] == []


@pytest.mark.parametrize("terminal_event,terminal_status", [
    ("cancel_requested", "CANCELLED"),
    ("restaurant_rejected", "REJECTED"),
])
def test_late_payment_establishes_refund_due_for_unpaid_terminal_order(terminal_event, terminal_status):
    terminal = apply_order_event(new_order("O", 1000), event("close", terminal_event))
    assert terminal["refund_due_paise"] == 0

    paid = apply_order_event(terminal, event("late-payment", "payment_confirmed"))
    assert paid["status"] == terminal_status
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 1000

    refunded = apply_order_event(paid, event("refund", "refund_processed", amount_paise=1000))
    assert refunded["payment_status"] == "REFUNDED"
    assert refunded["refunded_paise"] == 1000


def test_fresh_payment_notification_cannot_revive_a_fully_refunded_order():
    refunded = apply_order_event(
        paid_cancelled_order(), event("refund", "refund_processed", amount_paise=1000)
    )
    updated = apply_order_event(refunded, event("late-payment", "payment_confirmed"))

    assert updated["payment_status"] == "REFUNDED"
    assert updated["refund_due_paise"] == updated["refunded_paise"] == 1000
    assert updated["processed_event_ids"] == ["refund", "late-payment"]


def test_partial_refunds_complete_only_at_full_due_and_keep_due_unchanged():
    order = paid_cancelled_order()
    for event_id, amount, expected_total, expected_status in [
        ("r1", 300, 300, "PAID"),
        ("r2", 200, 500, "PAID"),
        ("too-large", 501, 500, "PAID"),
        ("r3", 500, 1000, "REFUNDED"),
        ("after-full", 1, 1000, "REFUNDED"),
    ]:
        order = apply_order_event(order, event(event_id, "refund_processed", amount_paise=amount))
        assert order["refunded_paise"] == expected_total
        assert order["refund_due_paise"] == 1000
        assert order["payment_status"] == expected_status


def test_missing_refund_amount_is_recorded_once_without_refunding():
    notification = event("missing-amount", "refund_processed")
    once = apply_order_event(paid_cancelled_order(), notification)

    assert once["refunded_paise"] == 0
    assert once["processed_event_ids"] == ["missing-amount"]
    assert apply_order_event(once, notification) == once


@pytest.mark.parametrize("field,value", [
    ("total_paise", -1),
    ("total_paise", 1000.0),
    ("total_paise", True),
    ("total_paise", None),
    ("total_paise", "1000"),
    ("refund_due_paise", -1),
    ("refund_due_paise", 1001),
    ("refund_due_paise", True),
    ("refund_due_paise", "1000"),
    ("refunded_paise", -1),
    ("refunded_paise", 1001),
    ("refunded_paise", 1.0),
    ("refunded_paise", True),
    ("processed_event_ids", None),
    ("processed_event_ids", "old-id"),
    ("processed_event_ids", {}),
])
def test_invalid_order_accounting_or_history_is_not_modified(field, value):
    order = paid_cancelled_order()
    order[field] = value
    before = deepcopy(order)

    result = apply_order_event(order, event("refund", "refund_processed", amount_paise=100))
    assert result == before
    assert order == before


def test_refunded_balance_cannot_exceed_due_even_when_below_order_total():
    order = paid_cancelled_order()
    order.update(refund_due_paise=400, refunded_paise=500)

    assert apply_order_event(order, event("refund", "refund_processed", amount_paise=100)) == order


@pytest.mark.parametrize("missing_key", ["order_id", "total_paise", "status"])
def test_missing_required_order_field_is_not_fabricated(missing_key):
    order = new_order("O", 1000)
    del order[missing_key]

    assert apply_order_event(order, event("payment", "payment_confirmed")) == order


def test_minimal_valid_order_gets_accounting_defaults_for_a_valid_event():
    order = {"order_id": "O", "total_paise": 1000, "status": "PLACED"}
    before = deepcopy(order)
    updated = apply_order_event(order, event("payment", "payment_confirmed"))

    assert updated == {
        "order_id": "O", "total_paise": 1000, "status": "PLACED",
        "payment_status": "PAID", "refund_due_paise": 0,
        "refunded_paise": 0, "processed_event_ids": ["payment"],
    }
    assert order == before
