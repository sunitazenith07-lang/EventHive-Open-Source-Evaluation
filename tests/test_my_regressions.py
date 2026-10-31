"""Extra regression tests for refund handling and order transitions."""
from service import apply_order_event
from models import new_order


def make_paid_rejected_order(total=1000):
    order = new_order("ORD-T1", total)
    order = apply_order_event(order, {"type": "payment_confirmed", "event_id": "e1"})
    order = apply_order_event(order, {"type": "restaurant_rejected", "event_id": "e2"})
    return order


def refund(order, amount, event_id):
    return apply_order_event(
        order, {"type": "refund_processed", "event_id": event_id, "amount_paise": amount}
    )


def test_refund_replay_same_event_id_not_applied_twice():
    order = make_paid_rejected_order()
    order = refund(order, 400, "r1")
    order = refund(order, 400, "r1")  # replay
    assert order["refunded_paise"] == 400


def test_refund_after_full_refund_is_ignored():
    order = make_paid_rejected_order()
    order = refund(order, 1000, "r1")
    assert order["payment_status"] == "REFUNDED"
    order = refund(order, 100, "r2")
    assert order["refunded_paise"] == 1000


def test_refund_exactly_equal_to_remaining_completes_refund():
    order = make_paid_rejected_order()
    order = refund(order, 400, "r1")
    order = refund(order, 600, "r2")
    assert order["refunded_paise"] == 1000
    assert order["payment_status"] == "REFUNDED"


def test_refund_one_paisa_over_remaining_is_ignored():
    order = make_paid_rejected_order()
    order = refund(order, 400, "r1")
    order = refund(order, 601, "r2")
    assert order["refunded_paise"] == 400


def test_cancel_after_dispatch_is_ignored():
    order = new_order("ORD-T2", 1000)
    for i, t in enumerate(["restaurant_accepted", "dispatch_started", "cancel_requested"]):
        order = apply_order_event(order, {"type": t, "event_id": f"x{i}"})
    assert order["status"] == "OUT_FOR_DELIVERY"


def test_apply_order_event_does_not_mutate_input():
    order = make_paid_rejected_order()
    before = dict(order)
    refund(order, 100, "r1")
    assert order["refunded_paise"] == before["refunded_paise"]