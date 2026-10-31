"""Regression and edge-case test suite for OrderOps service."""
from models import new_order
from service import apply_order_event, reconcile_orders


def test_edge_case_late_payment_after_restaurant_rejection():
    """Verifies late payment confirmation on rejected orders marks refund_due_paise properly."""
    order = new_order("O-REJ", 4500, "PLACED")
    order = apply_order_event(order, {"event_id": "E1", "type": "restaurant_rejected"})
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "UNPAID"
    assert order["refund_due_paise"] == 0

    order = apply_order_event(order, {"event_id": "E2", "type": "payment_confirmed"})
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 4500


def test_edge_case_late_payment_after_cancellation():
    """Verifies late payment confirmation on cancelled orders marks refund_due_paise."""
    order = new_order("O-CAN", 3000, "PLACED")
    order = apply_order_event(order, {"event_id": "E1", "type": "cancel_requested"})
    assert order["status"] == "CANCELLED"
    assert order["payment_status"] == "UNPAID"
    assert order["refund_due_paise"] == 0

    order = apply_order_event(order, {"event_id": "E2", "type": "payment_confirmed"})
    assert order["status"] == "CANCELLED"
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 3000


def test_edge_case_boolean_amount_in_refund_ignored():
    """Verifies Python boolean subclass trap (True/False) does not mutate paise."""
    order = new_order("O-BOOL", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    res_true = apply_order_event(order, {"event_id": "R1", "type": "refund_processed", "amount_paise": True})
    assert res_true["refunded_paise"] == 0
    assert res_true["payment_status"] == "PAID"

    res_false = apply_order_event(order, {"event_id": "R2", "type": "refund_processed", "amount_paise": False})
    assert res_false["refunded_paise"] == 0
    assert res_false["payment_status"] == "PAID"


def test_edge_case_multi_step_partial_refunds_and_over_refund():
    """Validates multi-step partial refunds and asserts over-refunding is blocked."""
    order = new_order("O-REF", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    # First partial refund
    step1 = apply_order_event(order, {"event_id": "R1", "type": "refund_processed", "amount_paise": 2000})
    assert step1["refunded_paise"] == 2000
    assert step1["payment_status"] == "PAID"

    # Attempt over-refund (remaining is 3000, attempt 3500)
    over = apply_order_event(step1, {"event_id": "R-OVER", "type": "refund_processed", "amount_paise": 3500})
    assert over["refunded_paise"] == 2000
    assert over["payment_status"] == "PAID"

    # Second partial refund completing 5000
    step2 = apply_order_event(step1, {"event_id": "R2", "type": "refund_processed", "amount_paise": 3000})
    assert step2["refunded_paise"] == 5000
    assert step2["payment_status"] == "REFUNDED"


def test_edge_case_cancellation_after_dispatch_and_delivered_ignored():
    """Protects dispatched and delivered orders from customer cancellation."""
    order_ofd = new_order("O-OFD", 2500, "OUT_FOR_DELIVERY")
    res1 = apply_order_event(order_ofd, {"event_id": "C1", "type": "cancel_requested"})
    assert res1["status"] == "OUT_FOR_DELIVERY"
    assert res1["refund_due_paise"] == 0

    order_del = new_order("O-DEL", 2500, "DELIVERED")
    res2 = apply_order_event(order_del, {"event_id": "C2", "type": "cancel_requested"})
    assert res2["status"] == "DELIVERED"
    assert res2["refund_due_paise"] == 0


def test_edge_case_reconcile_simultaneous_amount_and_status_mismatch():
    """Tests independent reporting when both amount and status differ."""
    internal = [{"order_id": "O-SIM", "total_paise": 5000, "status": "PLACED"}]
    provider = [{"order_id": "O-SIM", "amount_paise": 7000, "status": "DELIVERED"}]
    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["O-SIM"]
    assert report["status_mismatches"] == ["O-SIM"]
    assert report["matched"] == []


def test_edge_case_malformed_and_none_events():
    """Ensures system resilience against None, empty dictionaries, or unexpected event types without raising exceptions."""
    order = new_order("O-MAL", 1000, "PLACED")
    # None event
    res1 = apply_order_event(order, None)
    assert res1["status"] == "PLACED"
    # Non-dict event
    res2 = apply_order_event(order, "not-a-dict")
    assert res2["status"] == "PLACED"
    # Empty dict event
    res3 = apply_order_event(order, {})
    assert res3["status"] == "PLACED"
    # Unexpected event type
    res4 = apply_order_event(order, {"event_id": "UNK", "type": "random_unknown_type"})
    assert res4["status"] == "PLACED"

