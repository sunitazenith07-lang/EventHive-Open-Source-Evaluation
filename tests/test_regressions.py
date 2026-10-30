"""Regression tests for OrderOps: each test names the defect or decision it protects."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def cancelled_paid_order(total=1000):
    order = new_order("O", total, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=total)
    return order


# --- Idempotency -----------------------------------------------------------

def test_replayed_refund_event_is_applied_only_once():
    refund = ev("r1", "refund_processed", amount_paise=400)
    once = apply_order_event(cancelled_paid_order(), refund)
    twice = apply_order_event(once, refund)
    assert twice["refunded_paise"] == 400
    assert twice["processed_event_ids"] == ["r1"]


@pytest.mark.parametrize("bad_id", [None, "", True, [], 1.5])
def test_event_without_usable_id_is_ignored(bad_id):
    order = new_order("O", 1000)
    result = apply_order_event(order, ev(bad_id, "payment_confirmed"))
    assert result["payment_status"] == "UNPAID"
    assert result["processed_event_ids"] == []


def test_event_missing_id_key_is_ignored():
    order = new_order("O", 1000)
    result = apply_order_event(order, {"type": "payment_confirmed"})
    assert result == order


@pytest.mark.parametrize("bad_event", [None, "payment_confirmed", 5, []])
def test_non_dict_event_leaves_order_unchanged(bad_event):
    order = new_order("O", 1000)
    assert apply_order_event(order, bad_event) == order


def test_rejected_refund_id_is_still_recorded_so_it_cannot_be_retried():
    # Documented decision: every event with a usable id is recorded once seen.
    order = new_order("O", 1000)  # PLACED/UNPAID: not refundable yet
    first = apply_order_event(order, ev("r1", "refund_processed", amount_paise=500))
    assert first["refunded_paise"] == 0
    assert first["processed_event_ids"] == ["r1"]


# --- Refund safety ---------------------------------------------------------

def test_refund_after_full_refund_is_ignored():
    order = apply_order_event(cancelled_paid_order(), ev("r1", "refund_processed", amount_paise=1000))
    assert order["payment_status"] == "REFUNDED"
    again = apply_order_event(order, ev("r2", "refund_processed", amount_paise=1))
    assert again["refunded_paise"] == 1000
    assert again["payment_status"] == "REFUNDED"


def test_two_partial_refunds_sum_to_full_and_complete_the_refund():
    order = apply_order_event(cancelled_paid_order(), ev("r1", "refund_processed", amount_paise=400))
    assert order["payment_status"] == "PAID"
    order = apply_order_event(order, ev("r2", "refund_processed", amount_paise=600))
    assert order["refunded_paise"] == 1000
    assert order["payment_status"] == "REFUNDED"


@pytest.mark.parametrize("amount", [1000.0, 5.0, "500", None, True])
def test_non_integer_refund_amounts_are_rejected_even_if_numerically_valid(amount):
    result = apply_order_event(cancelled_paid_order(), ev("r1", "refund_processed", amount_paise=amount))
    assert result["refunded_paise"] == 0
    assert result["payment_status"] == "PAID"


def test_refund_event_without_amount_key_is_ignored():
    result = apply_order_event(cancelled_paid_order(), ev("r1", "refund_processed"))
    assert result["refunded_paise"] == 0


# --- Payment handling ------------------------------------------------------

def test_late_payment_confirmation_does_not_undo_refunded_status():
    order = apply_order_event(cancelled_paid_order(), ev("r1", "refund_processed", amount_paise=1000))
    result = apply_order_event(order, ev("p2", "payment_confirmed"))
    assert result["payment_status"] == "REFUNDED"
    assert result["refunded_paise"] == 1000


def test_payment_after_cancellation_creates_refund_due_and_allows_refund():
    order = new_order("O", 1000, "CANCELLED")
    paid = apply_order_event(order, ev("p1", "payment_confirmed"))
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 1000
    refunded = apply_order_event(paid, ev("r1", "refund_processed", amount_paise=1000))
    assert refunded["payment_status"] == "REFUNDED"


def test_payment_before_dispatch_creates_no_refund_due():
    paid = apply_order_event(new_order("O", 1000, "ACCEPTED"), ev("p1", "payment_confirmed"))
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 0


# --- Reconciliation --------------------------------------------------------

def test_order_differing_in_amount_and_status_is_reported_in_both_lists():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 90, "status": "DELIVERED"}],
    )
    assert report["amount_mismatches"] == ["A"]
    assert report["status_mismatches"] == ["A"]
    assert report["matched"] == []


def test_mixed_id_types_do_not_crash_and_sort_deterministically():
    rows = [{"order_id": 7, "amount_paise": 1, "status": "X"},
            {"order_id": "A", "amount_paise": 1, "status": "X"},
            {"order_id": 10, "amount_paise": 1, "status": "X"}]
    first = reconcile_orders(rows, rows)
    second = reconcile_orders(list(reversed(rows)), list(reversed(rows)))
    assert first == second
    assert first["matched"] == [10, 7, "A"]  # sorted as strings: "10" < "7" < "A"


@pytest.mark.parametrize("bad_row", [{}, {"order_id": None}, {"order_id": ""}, None, "text", {"order_id": [1]}])
def test_rows_without_a_usable_order_id_are_skipped(bad_row):
    good = {"order_id": "A", "amount_paise": 1, "status": "PLACED"}
    report = reconcile_orders([good, bad_row], [good, bad_row])
    assert report["matched"] == ["A"]
    assert report["missing_from_internal"] == []
    assert report["missing_from_provider"] == []


def test_none_inputs_behave_like_empty_lists():
    report = reconcile_orders(None, None)
    assert all(v == [] for v in report.values())


def test_internal_order_from_new_order_uses_total_paise_as_amount():
    internal = [new_order("A", 45900)]
    provider = [{"order_id": "A", "amount_paise": 45900, "status": "PLACED"}]
    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["A"]
    assert report["amount_mismatches"] == []


def test_zero_amount_is_compared_not_treated_as_missing():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 0, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 500, "status": "PLACED"}],
    )
    assert report["amount_mismatches"] == ["A"]