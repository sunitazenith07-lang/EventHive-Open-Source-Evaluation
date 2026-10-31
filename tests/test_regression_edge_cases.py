"""Regression tests covering specific edge cases and defects in OrderOps."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def test_edge_case_late_payment_after_restaurant_rejection():
    """Edge Case 1: Payment confirmation webhook arrives after restaurant rejection.
    
    Expected: Status remains REJECTED, payment becomes PAID, and full refund_due_paise
    is recorded so that the customer is eligible for a refund.
    """
    order = new_order("ORD-EDGE-1", 4500, "PLACED")
    # Step 1: Restaurant rejects while payment is still UNPAID
    order = apply_order_event(order, {"event_id": "EV-REJ", "type": "restaurant_rejected"})
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "UNPAID"
    assert order["refund_due_paise"] == 0

    # Step 2: Late payment webhook arrives
    order = apply_order_event(order, {"event_id": "EV-PAY", "type": "payment_confirmed"})
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 4500

    # Step 3: Refund can now be processed successfully
    order = apply_order_event(order, {"event_id": "EV-REF", "type": "refund_processed", "amount_paise": 4500})
    assert order["refunded_paise"] == 4500
    assert order["payment_status"] == "REFUNDED"


def test_edge_case_late_payment_after_cancellation():
    """Edge Case 2: Payment confirmation webhook arrives after customer cancelled."""
    order = new_order("ORD-EDGE-2", 3000, "PLACED")
    order = apply_order_event(order, {"event_id": "EV-CAN", "type": "cancel_requested"})
    assert order["status"] == "CANCELLED"
    assert order["payment_status"] == "UNPAID"
    assert order["refund_due_paise"] == 0

    order = apply_order_event(order, {"event_id": "EV-PAY", "type": "payment_confirmed"})
    assert order["status"] == "CANCELLED"
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 3000


def test_edge_case_boolean_amount_in_refund_ignored():
    """Edge Case 3: In Python, bool inherits from int (isinstance(True, int) is True).
    A boolean amount like True or False must be ignored as an invalid refund amount.
    """
    order = new_order("ORD-EDGE-3", 2000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=2000)

    # Attempting refund with True
    out_true = apply_order_event(order, {"event_id": "EV-B1", "type": "refund_processed", "amount_paise": True})
    assert out_true["refunded_paise"] == 0
    assert out_true["payment_status"] == "PAID"

    # Attempting refund with False
    out_false = apply_order_event(order, {"event_id": "EV-B2", "type": "refund_processed", "amount_paise": False})
    assert out_false["refunded_paise"] == 0
    assert out_false["payment_status"] == "PAID"


def test_edge_case_multi_step_partial_refunds_and_over_refund():
    """Edge Case 4: Multiple partial refunds reaching exact limit, followed by an excessive refund."""
    order = new_order("ORD-EDGE-4", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    # First partial refund: 2000
    order = apply_order_event(order, {"event_id": "R1", "type": "refund_processed", "amount_paise": 2000})
    assert order["refunded_paise"] == 2000
    assert order["payment_status"] == "PAID"  # remains partial

    # Second partial refund: 3000 (completes due amount)
    order = apply_order_event(order, {"event_id": "R2", "type": "refund_processed", "amount_paise": 3000})
    assert order["refunded_paise"] == 5000
    assert order["payment_status"] == "REFUNDED"

    # Subsequent refund attempt: 500 (exceeds balance)
    order = apply_order_event(order, {"event_id": "R3", "type": "refund_processed", "amount_paise": 500})
    assert order["refunded_paise"] == 5000
    assert order["payment_status"] == "REFUNDED"


def test_edge_case_cancellation_after_dispatch_and_delivered_ignored():
    """Edge Case 5: An order cannot be cancelled once dispatched or delivered."""
    # Out for delivery
    order1 = new_order("ORD-EDGE-5A", 1500, "OUT_FOR_DELIVERY")
    order1 = apply_order_event(order1, {"event_id": "CAN-1", "type": "cancel_requested"})
    assert order1["status"] == "OUT_FOR_DELIVERY"
    assert order1["refund_due_paise"] == 0

    # Delivered
    order2 = new_order("ORD-EDGE-5B", 1500, "DELIVERED")
    order2 = apply_order_event(order2, {"event_id": "CAN-2", "type": "cancel_requested"})
    assert order2["status"] == "DELIVERED"
    assert order2["refund_due_paise"] == 0


def test_edge_case_reconcile_simultaneous_amount_and_status_mismatch():
    """Edge Case 6: Order with both an amount mismatch and a status mismatch
    must appear in both mismatch lists and never in matched.
    """
    internal = [{"order_id": "ORD-EDGE-6", "total_paise": 5000, "status": "PLACED"}]
    provider = [{"order_id": "ORD-EDGE-6", "amount_paise": 7000, "status": "DELIVERED"}]

    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-EDGE-6"]
    assert report["status_mismatches"] == ["ORD-EDGE-6"]
    assert report["matched"] == []


def test_edge_case_malformed_and_none_events():
    """Edge Case 7: Malformed event structures (None, non-dict, missing type) do not corrupt state."""
    order = new_order("ORD-EDGE-7", 1000, "PLACED")
    before = dict(order)

    # Non-dict event
    res1 = apply_order_event(order, None)
    assert res1 == before

    # Empty dict
    res2 = apply_order_event(order, {})
    assert res2 == before

    # Unknown type
    res3 = apply_order_event(order, {"event_id": "EV-X", "type": "unknown_random_action"})
    assert res3["status"] == "PLACED"
    assert res3["processed_event_ids"] == ["EV-X"]
