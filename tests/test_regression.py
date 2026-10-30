"""Comprehensive regression tests for OrderOps lifecycle, refund safety, and reconciliation."""
import json
from pathlib import Path
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders, export_awaiting_refund_csv


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_customer_cancels_before_dispatch_paid():
    order = new_order("ORD-TEST-1", 3000)
    order = apply_order_event(order, ev("E1", "payment_confirmed"))
    assert order["payment_status"] == "PAID"
    assert order["status"] == "PLACED"

    order = apply_order_event(order, ev("E2", "cancel_requested"))
    assert order["status"] == "CANCELLED"
    assert order["refund_due_paise"] == 3000
    assert order["refunded_paise"] == 0


def test_cancellation_after_dispatch_is_ignored():
    order = new_order("ORD-TEST-2", 4500)
    order = apply_order_event(order, ev("E1", "restaurant_accepted"))
    order = apply_order_event(order, ev("E2", "dispatch_started"))
    assert order["status"] == "OUT_FOR_DELIVERY"

    # Cancellation request after dispatch must not transition to CANCELLED
    updated = apply_order_event(order, ev("E3", "cancel_requested"))
    assert updated["status"] == "OUT_FOR_DELIVERY"
    assert updated["refund_due_paise"] == 0


def test_restaurant_rejects_unpaid_order():
    order = new_order("ORD-TEST-3", 2500)
    assert order["payment_status"] == "UNPAID"

    updated = apply_order_event(order, ev("E1", "restaurant_rejected"))
    assert updated["status"] == "REJECTED"
    assert updated["refund_due_paise"] == 0


def test_restaurant_rejects_paid_order():
    order = new_order("ORD-TEST-4", 2500)
    order = apply_order_event(order, ev("E1", "payment_confirmed"))
    assert order["payment_status"] == "PAID"

    updated = apply_order_event(order, ev("E2", "restaurant_rejected"))
    assert updated["status"] == "REJECTED"
    assert updated["refund_due_paise"] == 2500


def test_late_payment_after_rejection_activates_refund_due():
    # Out of order: rejection occurs before payment_confirmed arrives
    order = new_order("ORD-TEST-5", 1500)
    order = apply_order_event(order, ev("E1", "restaurant_rejected"))
    assert order["status"] == "REJECTED"
    assert order["refund_due_paise"] == 0

    order = apply_order_event(order, ev("E2", "payment_confirmed"))
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 1500


def test_duplicate_event_idempotency_does_not_double_count():
    order = new_order("ORD-TEST-6", 2000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=2000)

    # First refund event
    step1 = apply_order_event(order, ev("REF-1", "refund_processed", amount_paise=1000))
    assert step1["refunded_paise"] == 1000
    assert step1["processed_event_ids"] == ["REF-1"]

    # Replay identical event
    step2 = apply_order_event(step1, ev("REF-1", "refund_processed", amount_paise=1000))
    assert step2["refunded_paise"] == 1000
    assert step2["processed_event_ids"] == ["REF-1"]


def test_partial_refund_then_full_refund_flow():
    order = new_order("ORD-TEST-7", 10000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=10000)

    # Partial refund 1: 4000
    step1 = apply_order_event(order, ev("R1", "refund_processed", amount_paise=4000))
    assert step1["refunded_paise"] == 4000
    assert step1["payment_status"] == "PAID"

    # Partial refund 2: 6000 (completes due)
    step2 = apply_order_event(step1, ev("R2", "refund_processed", amount_paise=6000))
    assert step2["refunded_paise"] == 10000
    assert step2["payment_status"] == "REFUNDED"

    # Attempt further refund after complete: must be rejected
    step3 = apply_order_event(step2, ev("R3", "refund_processed", amount_paise=100))
    assert step3["refunded_paise"] == 10000
    assert step3["payment_status"] == "REFUNDED"


def test_cumulative_refund_exceeding_due_is_rejected():
    order = new_order("ORD-TEST-8", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    step1 = apply_order_event(order, ev("R1", "refund_processed", amount_paise=3000))
    assert step1["refunded_paise"] == 3000

    # 3000 + 2500 = 5500 > 5000 -> rejected
    step2 = apply_order_event(step1, ev("R2", "refund_processed", amount_paise=2500))
    assert step2["refunded_paise"] == 3000
    assert step2["payment_status"] == "PAID"


def test_missing_event_id_and_repeated_conflicting_payload():
    order = new_order("ORD-TEST-9", 3000)
    # Event missing event_id processes cleanly without adding None to processed_event_ids
    step1 = apply_order_event(order, {"type": "payment_confirmed"})
    assert step1["payment_status"] == "PAID"
    assert None not in step1["processed_event_ids"]

    # First event with id "EV-CONFLICT"
    step2 = apply_order_event(step1, ev("EV-CONFLICT", "restaurant_accepted"))
    assert step2["status"] == "ACCEPTED"
    assert step2["processed_event_ids"] == ["EV-CONFLICT"]

    # Repeated event with identical event_id but conflicting payload (attempts restaurant_rejected)
    step3 = apply_order_event(step2, ev("EV-CONFLICT", "restaurant_rejected"))
    # Must be safely ignored due to idempotency by event_id
    assert step3["status"] == "ACCEPTED"
    assert step3["processed_event_ids"] == ["EV-CONFLICT"]


def test_boundary_order_amounts_integer_paise():
    # 1 paisa order boundary
    order_1p = new_order("ORD-1P", 1, "CANCELLED")
    order_1p.update(payment_status="PAID", refund_due_paise=1)
    res_1p = apply_order_event(order_1p, ev("R1", "refund_processed", amount_paise=1))
    assert res_1p["refunded_paise"] == 1
    assert res_1p["payment_status"] == "REFUNDED"

    # Reject 0 paisa refund
    order_zero = new_order("ORD-ZERO", 5000, "CANCELLED")
    order_zero.update(payment_status="PAID", refund_due_paise=5000)
    res_zero = apply_order_event(order_zero, ev("RZ", "refund_processed", amount_paise=0))
    assert res_zero["refunded_paise"] == 0


def test_reconciliation_simultaneous_amount_and_status_mismatch():
    internal = [{"order_id": "ORD-BOTH", "amount_paise": 5000, "status": "PLACED"}]
    provider = [{"order_id": "ORD-BOTH", "amount_paise": 6000, "status": "CANCELLED"}]

    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-BOTH"]
    assert report["status_mismatches"] == ["ORD-BOTH"]
    assert report["matched"] == []


def test_reconciliation_handles_none_and_malformed_records():
    internal = [None, "invalid", {"order_id": None}, {"order_id": "O1", "total_paise": 100, "status": "PLACED"}]
    provider = [None, {"foo": "bar"}, {"order_id": "O1", "amount_paise": 100, "status": "PLACED"}]

    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["O1"]
    assert report["missing_from_provider"] == []
    assert report["missing_from_internal"] == []


def test_export_awaiting_refund_csv():
    orders = [
        {"order_id": "O1", "status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 5000, "refunded_paise": 2000},
        {"order_id": "O2", "status": "DELIVERED", "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0},
        {"order_id": "O3", "status": "REJECTED", "payment_status": "REFUNDED", "refund_due_paise": 3000, "refunded_paise": 3000},
        {"order_id": "O4", "status": "REJECTED", "payment_status": "PAID", "refund_due_paise": 4000, "refunded_paise": 0},
    ]
    csv_text = export_awaiting_refund_csv(orders)
    lines = csv_text.splitlines()
    assert lines[0] == "order_id,status,payment_status,refund_due_paise,refunded_paise,outstanding_paise"
    assert len(lines) == 3  # Header + O1 (outstanding 3000) + O4 (outstanding 4000)
    assert "O1,CANCELLED,PAID,5000,2000,3000" in lines
    assert "O4,REJECTED,PAID,4000,0,4000" in lines


def test_process_full_synthetic_dataset_records():
    dataset_path = Path(__file__).resolve().parent.parent / "data" / "records.json"
    if not dataset_path.exists():
        pytest.skip("Dataset records.json not present")
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    orders = {o["order_id"]: dict(o) for o in data["orders"]}
    for event in data["events"]:
        oid = event.get("order_id")
        if oid in orders:
            orders[oid] = apply_order_event(orders[oid], event)

    report = reconcile_orders(list(orders.values()), data["provider_records"])
    assert len(report["matched"]) == 87
    assert len(report["missing_from_provider"]) == 12
    assert len(report["missing_from_internal"]) == 25
    assert len(report["amount_mismatches"]) == 20
    assert len(report["status_mismatches"]) == 33
