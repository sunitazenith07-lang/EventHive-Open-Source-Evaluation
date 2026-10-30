"""Regression and edge case tests for OrderOps."""
import json
from pathlib import Path
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders, export_awaiting_refund_csv


def make_event(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_duplicate_event_payload_conflict_is_ignored():
    """Edge Case 1: Replayed event with conflicting payload is ignored by idempotency."""
    order = new_order("O-01", 3000)
    e1 = make_event("EV-1", "payment_confirmed")
    res1 = apply_order_event(order, e1)
    assert res1["payment_status"] == "PAID"
    assert res1["processed_event_ids"] == ["EV-1"]

    # Replay same event ID with a conflicting type
    e1_conflict = make_event("EV-1", "restaurant_accepted")
    res2 = apply_order_event(res1, e1_conflict)
    assert res2["status"] == "PLACED"  # Status must NOT have changed to ACCEPTED
    assert res2["processed_event_ids"] == ["EV-1"]


def test_late_payment_confirmed_after_rejection_or_cancellation():
    """Edge Case 2: Late payment confirmation after order cancellation/rejection updates refund_due."""
    # Case A: Cancellation before payment
    order_cancel = new_order("O-02", 4500, "PLACED")
    order_cancel = apply_order_event(order_cancel, make_event("EV-C", "cancel_requested"))
    assert order_cancel["status"] == "CANCELLED"
    assert order_cancel["payment_status"] == "UNPAID"
    assert order_cancel["refund_due_paise"] == 0

    order_cancel_paid = apply_order_event(order_cancel, make_event("EV-P", "payment_confirmed"))
    assert order_cancel_paid["payment_status"] == "PAID"
    assert order_cancel_paid["refund_due_paise"] == 4500

    # Case B: Rejection before payment
    order_reject = new_order("O-03", 2500, "PLACED")
    order_reject = apply_order_event(order_reject, make_event("EV-R", "restaurant_rejected"))
    assert order_reject["status"] == "REJECTED"
    assert order_reject["payment_status"] == "UNPAID"
    assert order_reject["refund_due_paise"] == 0

    order_reject_paid = apply_order_event(order_reject, make_event("EV-P2", "payment_confirmed"))
    assert order_reject_paid["payment_status"] == "PAID"
    assert order_reject_paid["refund_due_paise"] == 2500


def test_payment_confirmed_does_not_revert_refunded_status():
    """Edge Case 3: Payment confirmation arriving after full refund does not revert REFUNDED status."""
    order = new_order("O-04", 2000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=2000)
    refunded = apply_order_event(order, make_event("EV-REF", "refund_processed", amount_paise=2000))
    assert refunded["payment_status"] == "REFUNDED"
    assert refunded["refunded_paise"] == 2000

    late_payment = apply_order_event(refunded, make_event("EV-LATE-PAY", "payment_confirmed"))
    assert late_payment["payment_status"] == "REFUNDED"


def test_cancellation_after_dispatch_is_safely_ignored():
    """Edge Case 4: Cancellation request arriving after dispatch or delivery is ignored."""
    order = new_order("O-05", 5000, "ACCEPTED")
    dispatched = apply_order_event(order, make_event("EV-D", "dispatch_started"))
    assert dispatched["status"] == "OUT_FOR_DELIVERY"

    # Attempt cancel while out for delivery
    cancel_attempt_1 = apply_order_event(dispatched, make_event("EV-C1", "cancel_requested"))
    assert cancel_attempt_1["status"] == "OUT_FOR_DELIVERY"

    # Complete delivery
    delivered = apply_order_event(cancel_attempt_1, make_event("EV-DEL", "order_delivered"))
    assert delivered["status"] == "DELIVERED"

    # Attempt cancel after delivery
    cancel_attempt_2 = apply_order_event(delivered, make_event("EV-C2", "cancel_requested"))
    assert cancel_attempt_2["status"] == "DELIVERED"


def test_multi_step_partial_refunds_and_overpayment_protection():
    """Edge Case 5: Cumulative partial refunds transition to REFUNDED only when exact total reached."""
    order = new_order("O-06", 6000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=6000)

    # Step 1: Partial refund 2500
    s1 = apply_order_event(order, make_event("R1", "refund_processed", amount_paise=2500))
    assert s1["refunded_paise"] == 2500
    assert s1["payment_status"] == "PAID"

    # Step 2: Attempt refund 4000 (exceeds remaining 3500) -> ignored
    s2 = apply_order_event(s1, make_event("R2", "refund_processed", amount_paise=4000))
    assert s2["refunded_paise"] == 2500
    assert s2["payment_status"] == "PAID"

    # Step 3: Partial refund 2000
    s3 = apply_order_event(s2, make_event("R3", "refund_processed", amount_paise=2000))
    assert s3["refunded_paise"] == 4500
    assert s3["payment_status"] == "PAID"

    # Step 4: Final refund 1500 (completes full 6000 due)
    s4 = apply_order_event(s3, make_event("R4", "refund_processed", amount_paise=1500))
    assert s4["refunded_paise"] == 6000
    assert s4["payment_status"] == "REFUNDED"


def test_malformed_event_and_empty_inputs():
    """Edge Case 6: Empty orders, non-dict inputs, missing event_id or unknown fields."""
    # Non-dict inputs
    assert apply_order_event({}, None) == {
        "payment_status": "UNPAID",
        "refund_due_paise": 0,
        "refunded_paise": 0,
        "processed_event_ids": [],
    }
    assert apply_order_event(None, {}) == {
        "payment_status": "UNPAID",
        "refund_due_paise": 0,
        "refunded_paise": 0,
        "processed_event_ids": [],
    }

    # Event without event_id
    order = new_order("O-07", 1000)
    res = apply_order_event(order, {"type": "payment_confirmed"})
    assert res["payment_status"] == "PAID"
    assert res["processed_event_ids"] == []


def test_reconciliation_dual_mismatch_and_key_handling():
    """Edge Case 7: Simultaneous amount and status mismatch on single order."""
    internal = [{"order_id": "ORD-X", "total_paise": 1000, "status": "DELIVERED"}]
    provider = [{"order_id": "ORD-X", "amount_paise": 1200, "status": "CANCELLED"}]

    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-X"]
    assert report["status_mismatches"] == ["ORD-X"]
    assert report["matched"] == []
    assert report["missing_from_provider"] == []
    assert report["missing_from_internal"] == []


def test_full_dataset_reconciliation_from_records_json():
    """Verify reconciliation against the full synthetic dataset in data/records.json."""
    records_path = Path(__file__).resolve().parent.parent / "data" / "records.json"
    with open(records_path) as f:
        data = json.load(f)

    report = reconcile_orders(data["orders"], data["provider_records"])
    assert len(report["matched"]) == 107
    assert len(report["missing_from_provider"]) == 12
    assert len(report["missing_from_internal"]) == 25
    assert len(report["amount_mismatches"]) == 20
    assert len(report["status_mismatches"]) == 12

    # ORD-1078 is the known dual mismatch in the dataset
    assert "ORD-1078" in report["amount_mismatches"]
    assert "ORD-1078" in report["status_mismatches"]
    assert "ORD-1078" not in report["matched"]


def test_export_awaiting_refund_csv_stretch():
    """Test optional stretch feature: export awaiting refund orders to CSV."""
    orders = [
        {"order_id": "O-1", "status": "CANCELLED", "payment_status": "PAID", "total_paise": 5000, "refund_due_paise": 5000, "refunded_paise": 2000},
        {"order_id": "O-2", "status": "DELIVERED", "payment_status": "PAID", "total_paise": 3000, "refund_due_paise": 0, "refunded_paise": 0},
        {"order_id": "O-3", "status": "REJECTED", "payment_status": "PAID", "total_paise": 4000, "refund_due_paise": 4000, "refunded_paise": 4000},
        {"order_id": "O-4", "status": "CANCELLED", "payment_status": "UNPAID", "total_paise": 1500, "refund_due_paise": 0, "refunded_paise": 0},
        {"order_id": "O-5", "status": "CANCELLED", "payment_status": "PAID", "total_paise": 7000, "refund_due_paise": 7000, "refunded_paise": 0},
    ]

    csv_data = export_awaiting_refund_csv(orders)
    lines = csv_data.strip().split("\n")
    assert lines[0] == "order_id,status,payment_status,total_paise,refund_due_paise,refunded_paise,outstanding_paise"
    # O-1 and O-5 should be present; O-2 (delivered), O-3 (fully refunded), O-4 (unpaid) should not
    assert len(lines) == 3
    assert "O-1,CANCELLED,PAID,5000,5000,2000,3000" in lines
    assert "O-5,CANCELLED,PAID,7000,7000,0,7000" in lines
