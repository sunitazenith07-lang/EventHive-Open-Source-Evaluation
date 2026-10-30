import json
from pathlib import Path
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders, summarise_orders_by_state


def ev(event_id, kind, **extra):
    return {"event_id": event_id, "type": kind, **extra}


def test_idempotent_event_replay_preserves_event_list():
    order = new_order("ORD-REG-1", 5000)
    e = ev("EV-100", "payment_confirmed")
    res1 = apply_order_event(order, e)
    res2 = apply_order_event(res1, e)
    assert res2["processed_event_ids"] == ["EV-100"]
    assert res2["payment_status"] == "PAID"


def test_idempotent_refund_replay_does_not_duplicate_refund():
    order = new_order("ORD-REG-2", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    e = ev("RF-100", "refund_processed", amount_paise=2000)
    res1 = apply_order_event(order, e)
    assert res1["refunded_paise"] == 2000
    res2 = apply_order_event(res1, e)
    assert res2["refunded_paise"] == 2000
    assert res2["processed_event_ids"] == ["RF-100"]


@pytest.mark.parametrize("bad_amount", [-500, 0, 100.5, "1000", True, False, None, [], {}])
def test_refund_rejects_non_positive_or_non_integer(bad_amount):
    order = new_order("ORD-REG-3", 5000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=5000)
    res = apply_order_event(order, ev("RF-BAD", "refund_processed", amount_paise=bad_amount))
    assert res["refunded_paise"] == 0
    assert res["payment_status"] == "PAID"


def test_refund_exact_split_to_full():
    order = new_order("ORD-REG-4", 6000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=6000)
    r1 = apply_order_event(order, ev("RF-1", "refund_processed", amount_paise=2500))
    assert r1["refunded_paise"] == 2500
    assert r1["payment_status"] == "PAID"

    # Excess attempt should fail and not affect state
    r_bad = apply_order_event(r1, ev("RF-EXCESS", "refund_processed", amount_paise=4000))
    assert r_bad["refunded_paise"] == 2500
    assert r_bad["payment_status"] == "PAID"

    # Exact remaining should complete the refund
    r2 = apply_order_event(r1, ev("RF-2", "refund_processed", amount_paise=3500))
    assert r2["refunded_paise"] == 6000
    assert r2["payment_status"] == "REFUNDED"


def test_late_payment_confirmed_on_rejected_order_sets_refund_due():
    order = new_order("ORD-REG-5", 4200, "PLACED")
    rejected = apply_order_event(order, ev("EV-REJ", "restaurant_rejected"))
    assert rejected["status"] == "REJECTED"
    assert rejected["payment_status"] == "UNPAID"
    assert rejected["refund_due_paise"] == 0

    paid_later = apply_order_event(rejected, ev("EV-PAY", "payment_confirmed"))
    assert paid_later["status"] == "REJECTED"
    assert paid_later["payment_status"] == "PAID"
    assert paid_later["refund_due_paise"] == 4200


def test_cancel_after_dispatch_is_safely_ignored():
    order = new_order("ORD-REG-6", 3000, "PLACED")
    accepted = apply_order_event(order, ev("E1", "restaurant_accepted"))
    dispatched = apply_order_event(accepted, ev("E2", "dispatch_started"))
    assert dispatched["status"] == "OUT_FOR_DELIVERY"

    cancel_attempt = apply_order_event(dispatched, ev("E3", "cancel_requested"))
    assert cancel_attempt["status"] == "OUT_FOR_DELIVERY"
    assert cancel_attempt["refund_due_paise"] == 0

    delivered = apply_order_event(cancel_attempt, ev("E4", "order_delivered"))
    assert delivered["status"] == "DELIVERED"


def test_reconcile_orders_supports_both_key_conventions():
    internal = [{"order_id": "ORD-1", "total_paise": 5000, "status": "PLACED"}]
    provider = [{"order_id": "ORD-1", "amount_paise": 5000, "status": "PLACED"}]
    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["ORD-1"]
    assert report["amount_mismatches"] == []
    assert report["status_mismatches"] == []


def test_reconcile_orders_handles_simultaneous_amount_and_status_mismatch():
    internal = [{"order_id": "ORD-MISMATCH", "amount_paise": 2000, "status": "ACCEPTED"}]
    provider = [{"order_id": "ORD-MISMATCH", "amount_paise": 3000, "status": "DELIVERED"}]
    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-MISMATCH"]
    assert report["status_mismatches"] == ["ORD-MISMATCH"]
    assert report["matched"] == []


def test_reconcile_with_dataset_records():
    data_path = Path(__file__).parent.parent / "data" / "records.json"
    if not data_path.exists():
        pytest.skip("Dataset file not found")
    with open(data_path) as f:
        data = json.load(f)
    orders = data.get("orders", [])
    providers = data.get("provider_records", [])
    report = reconcile_orders(orders, providers)

    # Basic assertions verifying deterministic output
    assert isinstance(report["matched"], list)
    assert isinstance(report["missing_from_provider"], list)
    assert isinstance(report["missing_from_internal"], list)
    assert isinstance(report["amount_mismatches"], list)
    assert isinstance(report["status_mismatches"], list)
    assert len(report["matched"]) > 0


def test_summarise_orders_by_state_stretch():
    orders = [
        new_order("O1", 1000, "PLACED"),
        new_order("O2", 2000, "ACCEPTED"),
        new_order("O3", 3000, "PLACED"),
    ]
    summary = summarise_orders_by_state(orders)
    assert summary["PLACED:UNPAID"]["count"] == 2
    assert summary["PLACED:UNPAID"]["total_paise"] == 4000
    assert summary["ACCEPTED:UNPAID"]["count"] == 1
    assert summary["ACCEPTED:UNPAID"]["total_paise"] == 2000
