"""Additional unit tests and edge cases for order service and reconciliation."""
import json
import os
import tempfile
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders, export_awaiting_refund_csv


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_cancel_after_dispatch_ignored():
    # Customer tries to cancel after food is out for delivery
    order = new_order("ORD-DISPATCHED", 45000, "OUT_FOR_DELIVERY")
    order["payment_status"] = "PAID"
    order["refund_due_paise"] = 0

    res = apply_order_event(order, ev("E1", "cancel_requested"))
    assert res["status"] == "OUT_FOR_DELIVERY"
    assert res["payment_status"] == "PAID"
    assert res["refund_due_paise"] == 0
    assert res["refunded_paise"] == 0


def test_duplicate_event_with_same_id_is_ignored():
    # Replaying the exact same event_id should not change state again
    order = new_order("ORD-1", 30000, "PLACED")
    event1 = ev("EV-1", "payment_confirmed")
    order = apply_order_event(order, event1)
    assert order["payment_status"] == "PAID"
    assert order["processed_event_ids"] == ["EV-1"]

    # Same event_id with different payload
    dup_event = ev("EV-1", "restaurant_rejected")
    replayed = apply_order_event(order, dup_event)
    assert replayed["status"] == "PLACED"
    assert replayed["processed_event_ids"] == ["EV-1"]


def test_late_payment_after_cancellation():
    # Order cancelled first while unpaid, then payment webhook arrives late
    order = new_order("ORD-LATE", 15000, "PLACED")
    cancelled = apply_order_event(order, ev("E1", "cancel_requested"))
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["payment_status"] == "UNPAID"
    assert cancelled["refund_due_paise"] == 0

    paid = apply_order_event(cancelled, ev("E2", "payment_confirmed"))
    assert paid["status"] == "CANCELLED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 15000


def test_boolean_refund_amount_rejected():
    # True/False should not be treated as 1/0
    order = new_order("ORD-BOOL", 10000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=10000)

    for bad_val in [True, False, 100.5, "500", None, [100], {"amt": 100}]:
        res = apply_order_event(order, ev("E-BAD", "refund_processed", amount_paise=bad_val))
        assert res["refunded_paise"] == 0
        assert res["payment_status"] == "PAID"


def test_partial_refunds_and_over_limit():
    order = new_order("ORD-CUMULATIVE", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)

    # First partial refund of 2000 paise
    r1 = apply_order_event(order, ev("R1", "refund_processed", amount_paise=2000))
    assert r1["refunded_paise"] == 2000
    assert r1["payment_status"] == "PAID"

    # Trying to refund 3500 when only 3000 is left -> should be ignored
    r2 = apply_order_event(r1, ev("R2", "refund_processed", amount_paise=3500))
    assert r2["refunded_paise"] == 2000
    assert r2["payment_status"] == "PAID"

    # Completing the remaining 3000 paise -> marked REFUNDED
    r3 = apply_order_event(r2, ev("R3", "refund_processed", amount_paise=3000))
    assert r3["refunded_paise"] == 5000
    assert r3["payment_status"] == "REFUNDED"

    # Extra refund attempt after already refunded
    r4 = apply_order_event(r3, ev("R4", "refund_processed", amount_paise=1))
    assert r4["refunded_paise"] == 5000
    assert r4["payment_status"] == "REFUNDED"


def test_amount_and_status_mismatch_together():
    # Order has both wrong amount and wrong status
    internal = [{"order_id": "ORD-BOTH", "total_paise": 4000, "status": "ACCEPTED"}]
    provider = [{"order_id": "ORD-BOTH", "amount_paise": 3000, "status": "DELIVERED"}]

    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-BOTH"]
    assert report["status_mismatches"] == ["ORD-BOTH"]
    assert report["matched"] == []


def test_event_with_wrong_order_id():
    # Event explicitly meant for another order should not affect this one
    order = new_order("ORD-A", 10000, "PLACED")
    wrong_event = {"event_id": "E1", "order_id": "ORD-B", "type": "cancel_requested"}

    res = apply_order_event(order, wrong_event)
    assert res["status"] == "PLACED"
    assert "E1" not in res["processed_event_ids"]


def test_malformed_event_input():
    # Safe handling of invalid types
    assert apply_order_event(None, {"type": "cancel_requested"}) == {}
    order = new_order("ORD-TEST", 5000)
    assert apply_order_event(order, None)["order_id"] == "ORD-TEST"
    assert apply_order_event(order, "invalid")["order_id"] == "ORD-TEST"

    empty_report = reconcile_orders(None, None)
    assert empty_report["matched"] == []
    assert empty_report["missing_from_internal"] == []


def test_records_json_dataset():
    # Test with the provided synthetic data file records.json
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "records.json")
    if not os.path.exists(data_path):
        pytest.skip("records.json not found")

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = reconcile_orders(data["orders"], data["provider_records"])
    assert len(report["matched"]) == 107
    assert len(report["missing_from_provider"]) == 12
    assert len(report["missing_from_internal"]) == 25
    assert len(report["amount_mismatches"]) == 20
    assert len(report["status_mismatches"]) == 12
    assert set(report["amount_mismatches"]) & set(report["status_mismatches"]) == {"ORD-1078"}


def test_export_awaiting_refund_csv():
    orders = [
        {"order_id": "ORD-1", "status": "CANCELLED", "payment_status": "PAID", "total_paise": 5000, "refund_due_paise": 5000, "refunded_paise": 0},
        {"order_id": "ORD-2", "status": "REJECTED", "payment_status": "PAID", "total_paise": 4000, "refund_due_paise": 4000, "refunded_paise": 1500},
        {"order_id": "ORD-3", "status": "CANCELLED", "payment_status": "REFUNDED", "total_paise": 3000, "refund_due_paise": 3000, "refunded_paise": 3000},
    ]

    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".csv") as f:
        tmp_path = f.name

    try:
        csv_str = export_awaiting_refund_csv(orders, tmp_path)
        lines = csv_str.strip().split("\n")
        assert lines[0] == "order_id,status,payment_status,total_paise,refund_due_paise,refunded_paise,awaiting_refund_paise"
        assert len(lines) == 3
        assert "ORD-1,CANCELLED,PAID,5000,5000,0,5000" in lines
        assert "ORD-2,REJECTED,PAID,4000,4000,1500,2500" in lines
        assert "ORD-3" not in csv_str
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
