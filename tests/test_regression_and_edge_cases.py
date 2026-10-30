"""Regression and edge case test suite for OrderOps service."""
import pytest
import os
import tempfile
from models import new_order
from service import apply_order_event, reconcile_orders, export_awaiting_refund_csv


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_idempotency_across_different_event_types():
    """Ensure idempotency works for all event types, not just payment_confirmed."""
    order = new_order("ORD-TEST-1", 3000)
    
    # 1. Payment confirmation replay
    pay_event = ev("PAY-01", "payment_confirmed")
    order = apply_order_event(order, pay_event)
    order_replay = apply_order_event(order, pay_event)
    assert order_replay == order
    assert order_replay["processed_event_ids"] == ["PAY-01"]

    # 2. Acceptance replay
    accept_event = ev("ACC-01", "restaurant_accepted")
    order = apply_order_event(order, accept_event)
    order_replay = apply_order_event(order, accept_event)
    assert order_replay == order
    assert order_replay["processed_event_ids"] == ["PAY-01", "ACC-01"]

    # 3. Cancellation replay
    cancel_event = ev("CAN-01", "cancel_requested")
    order = apply_order_event(order, cancel_event)
    order_replay = apply_order_event(order, cancel_event)
    assert order_replay == order
    assert order_replay["processed_event_ids"] == ["PAY-01", "ACC-01", "CAN-01"]
    assert order_replay["refund_due_paise"] == 3000

    # 4. Refund replay
    ref_event = ev("REF-01", "refund_processed", amount_paise=1000)
    order = apply_order_event(order, ref_event)
    order_replay = apply_order_event(order, ref_event)
    assert order_replay == order
    assert order_replay["refunded_paise"] == 1000
    assert order_replay["processed_event_ids"] == ["PAY-01", "ACC-01", "CAN-01", "REF-01"]


def test_multiple_partial_refunds_reaching_exact_total():
    """Verify multiple valid partial refunds transition to REFUNDED only when fully paid."""
    order = new_order("ORD-PARTIAL", 6000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=6000)

    # 1st partial refund: 1500
    step1 = apply_order_event(order, ev("R1", "refund_processed", amount_paise=1500))
    assert step1["refunded_paise"] == 1500
    assert step1["payment_status"] == "PAID"

    # 2nd partial refund: 2500 -> total 4000
    step2 = apply_order_event(step1, ev("R2", "refund_processed", amount_paise=2500))
    assert step2["refunded_paise"] == 4000
    assert step2["payment_status"] == "PAID"

    # Attempt an over-refund (2500 remaining is only 2000) -> should be rejected
    step3_invalid = apply_order_event(step2, ev("R3-FAIL", "refund_processed", amount_paise=2500))
    assert step3_invalid["refunded_paise"] == 4000
    assert step3_invalid["payment_status"] == "PAID"

    # 3rd exact partial refund: 2000 -> total 6000
    step3 = apply_order_event(step2, ev("R3", "refund_processed", amount_paise=2000))
    assert step3["refunded_paise"] == 6000
    assert step3["payment_status"] == "REFUNDED"

    # Subsequent refund attempts after REFUNDED are rejected
    step4 = apply_order_event(step3, ev("R4", "refund_processed", amount_paise=100))
    assert step4["refunded_paise"] == 6000
    assert step4["payment_status"] == "REFUNDED"


def test_payment_confirmed_after_rejection_sets_refund_due():
    """If payment confirms after restaurant rejection, refund_due_paise must become total_paise."""
    order = new_order("ORD-LATE-PAY", 4500, "PLACED")
    order = apply_order_event(order, ev("E1", "restaurant_rejected"))
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "UNPAID"
    assert order["refund_due_paise"] == 0

    # Late payment arrives
    order = apply_order_event(order, ev("E2", "payment_confirmed"))
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 4500

    # Now refund is eligible and can be processed
    order = apply_order_event(order, ev("E3", "refund_processed", amount_paise=4500))
    assert order["refunded_paise"] == 4500
    assert order["payment_status"] == "REFUNDED"


def test_cannot_cancel_out_for_delivery_or_delivered():
    """Cancellation requests after dispatch must not alter order status or grant refunds."""
    # Out for delivery
    order_ofd = new_order("ORD-DISPATCHED", 2500, "OUT_FOR_DELIVERY")
    order_ofd.update(payment_status="PAID")
    res_ofd = apply_order_event(order_ofd, ev("C1", "cancel_requested"))
    assert res_ofd["status"] == "OUT_FOR_DELIVERY"
    assert res_ofd["refund_due_paise"] == 0

    # Delivered
    order_del = new_order("ORD-DONE", 2500, "DELIVERED")
    order_del.update(payment_status="PAID")
    res_del = apply_order_event(order_del, ev("C2", "cancel_requested"))
    assert res_del["status"] == "DELIVERED"
    assert res_del["refund_due_paise"] == 0


def test_boolean_and_type_coercion_safety_in_refunds():
    """Python booleans are subclasses of int; True and False must not be processed as 1 or 0 paise."""
    order = new_order("ORD-BOOL", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    res_true = apply_order_event(order, ev("B1", "refund_processed", amount_paise=True))
    assert res_true["refunded_paise"] == 0

    res_false = apply_order_event(order, ev("B2", "refund_processed", amount_paise=False))
    assert res_false["refunded_paise"] == 0


def test_safe_handling_of_malformed_and_none_inputs():
    """Verify empty/None inputs do not crash or corrupt state."""
    # None order
    assert apply_order_event(None, ev("E1", "payment_confirmed")) == {}
    
    # None event
    valid_order = new_order("ORD-SAFE", 1000)
    assert apply_order_event(valid_order, None) == valid_order

    # Missing event_id
    res_no_eid = apply_order_event(valid_order, {"type": "payment_confirmed"})
    assert res_no_eid["payment_status"] == "PAID"
    assert res_no_eid["processed_event_ids"] == []

    # Invalid event kind
    res_bad_kind = apply_order_event(valid_order, ev("E2", "invalid_action"))
    assert res_bad_kind["status"] == "PLACED"
    assert "E2" in res_bad_kind["processed_event_ids"]


def test_reconciliation_simultaneous_amount_and_status_mismatch():
    """An order with both amount mismatch and status mismatch must appear in both categories."""
    internal = [{"order_id": "ORD-BOTH", "total_paise": 5000, "status": "ACCEPTED"}]
    provider = [{"order_id": "ORD-BOTH", "amount_paise": 4000, "status": "CANCELLED"}]

    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-BOTH"]
    assert report["status_mismatches"] == ["ORD-BOTH"]
    assert report["matched"] == []
    assert report["missing_from_internal"] == []
    assert report["missing_from_provider"] == []


def test_reconciliation_supports_both_total_paise_and_amount_paise():
    """Internal summaries may use total_paise or amount_paise."""
    internal = [
        {"order_id": "O1", "total_paise": 1000, "status": "PLACED"},
        {"order_id": "O2", "amount_paise": 2000, "status": "ACCEPTED"},
    ]
    provider = [
        {"order_id": "O1", "amount_paise": 1000, "status": "PLACED"},
        {"order_id": "O2", "amount_paise": 2000, "status": "ACCEPTED"},
    ]

    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["O1", "O2"]
    assert report["amount_mismatches"] == []
    assert report["status_mismatches"] == []


def test_reconciliation_invalid_and_empty_inputs():
    """reconcile_orders handles malformed list records without crashing."""
    report = reconcile_orders(None, None)
    assert all(report[k] == [] for k in report)

    report2 = reconcile_orders([{"order_id": None}], [{"invalid": True}])
    assert all(report2[k] == [] for k in report2)


def test_stretch_export_awaiting_refund_csv():
    """Verify export_awaiting_refund_csv produces expected CSV with correct headers and filters."""
    orders = [
        # Awaiting refund: due=5000, refunded=2000 -> outstanding 3000
        {"order_id": "ORD-AWAIT-1", "total_paise": 5000, "status": "CANCELLED",
         "payment_status": "PAID", "refund_due_paise": 5000, "refunded_paise": 2000},
        # Fully refunded: due=3000, refunded=3000 -> outstanding 0 (should not be in CSV)
        {"order_id": "ORD-REFUNDED", "total_paise": 3000, "status": "CANCELLED",
         "payment_status": "REFUNDED", "refund_due_paise": 3000, "refunded_paise": 3000},
        # Not cancelled/unpaid: due=0, refunded=0 (should not be in CSV)
        {"order_id": "ORD-NORMAL", "total_paise": 4000, "status": "DELIVERED",
         "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0},
        # Another awaiting refund: due=1000, refunded=0 -> outstanding 1000
        {"order_id": "ORD-AWAIT-2", "total_paise": 1000, "status": "REJECTED",
         "payment_status": "PAID", "refund_due_paise": 1000, "refunded_paise": 0},
    ]

    csv_output = export_awaiting_refund_csv(orders)
    lines = csv_output.strip().split("\n")
    assert lines[0] == "order_id,total_paise,status,payment_status,refund_due_paise,refunded_paise,outstanding_refund_paise"
    assert len(lines) == 3  # header + 2 awaiting refund orders

    # Deterministic sorting check: ORD-AWAIT-1, then ORD-AWAIT-2
    assert "ORD-AWAIT-1,5000,CANCELLED,PAID,5000,2000,3000" == lines[1]
    assert "ORD-AWAIT-2,1000,REJECTED,PAID,1000,0,1000" == lines[2]

    # Verify file writing
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpfile = os.path.join(tmpdir, "awaiting_refunds.csv")
        export_awaiting_refund_csv(orders, filepath=tmpfile)
        assert os.path.exists(tmpfile)
        with open(tmpfile, "r", encoding="utf-8") as f:
            assert f.read() == csv_output
