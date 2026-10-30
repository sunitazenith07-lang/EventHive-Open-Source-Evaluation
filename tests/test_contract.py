from models import new_order
from service import apply_order_event, reconcile_orders


def event(event_id, kind, **extra):
    return {"event_id":event_id,"type":kind,**extra}


def test_accept_only_when_placed_and_does_not_mutate_input():
    order=new_order("O1",1000)
    updated=apply_order_event(order,event("e1","restaurant_accepted"))
    assert updated["status"]=="ACCEPTED"
    assert order["status"]=="PLACED"


def test_paid_rejected_order_records_full_refund_due():
    order=new_order("O1",1000)
    order["payment_status"]="PAID"
    out=apply_order_event(order,event("e1","restaurant_rejected"))
    assert out["status"]=="REJECTED"
    assert out["refund_due_paise"]==1000


def test_cancel_after_dispatch_is_ignored():
    order=new_order("O1",1000,"OUT_FOR_DELIVERY")
    out=apply_order_event(order,event("e1","cancel_requested"))
    assert out["status"]=="OUT_FOR_DELIVERY"


def test_duplicate_event_is_idempotent():
    order=new_order("O1",1000)
    e=event("e1","payment_confirmed")
    first=apply_order_event(order,e)
    second=apply_order_event(first,e)
    assert second["processed_event_ids"]==["e1"]


def test_refund_requires_eligible_order():
    out=apply_order_event(new_order("O1",1000),event("r1","refund_processed",amount_paise=500))
    assert out["refunded_paise"]==0
    assert out["payment_status"]=="UNPAID"


def test_refund_must_be_positive():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=1000)
    for amount in [0,-10]:
        out=apply_order_event(order,event("r1","refund_processed",amount_paise=amount))
        assert out["refunded_paise"]==0


def test_refund_cannot_exceed_amount_due():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=1000)
    out=apply_order_event(order,event("r1","refund_processed",amount_paise=1200))
    assert out["refunded_paise"]==0


def test_partial_refund_is_not_marked_complete():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=1000)
    out=apply_order_event(order,event("r1","refund_processed",amount_paise=400))
    assert out["refunded_paise"]==400
    assert out["payment_status"]=="PAID"


def test_delivery_state_flow():
    order=new_order("O1",1000)
    for e in [event("1","restaurant_accepted"),event("2","dispatch_started"),event("3","order_delivered")]:
        order=apply_order_event(order,e)
    assert order["status"]=="DELIVERED"


def test_reconcile_reports_missing_and_amount_difference():
    report=reconcile_orders([{"order_id":"A","amount_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":90,"status":"PLACED"},{"order_id":"B","amount_paise":50,"status":"PLACED"}])
    assert report["amount_mismatches"]==["A"]
    assert report["missing_from_internal"]==["B"]


def test_reconcile_reports_status_difference():
    report=reconcile_orders([{"order_id":"A","amount_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":100,"status":"DELIVERED"}])
    assert report["status_mismatches"]==["A"]
    assert report["matched"]==[]


def test_empty_reconciliation():
    assert all(v==[] for v in reconcile_orders([],[]).values())


# Regression tests for edge cases and dataset validation


def test_duplicate_event_with_conflicting_payload_is_ignored():
    order = new_order("O1", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    e1 = event("EV-DUP", "refund_processed", amount_paise=500)
    order_after = apply_order_event(order, e1)
    assert order_after["refunded_paise"] == 500
    # Replaying the same event_id with a conflicting payload must be ignored
    e_conflict = event("EV-DUP", "refund_processed", amount_paise=200)
    order_replayed = apply_order_event(order_after, e_conflict)
    assert order_replayed["refunded_paise"] == 500
    assert order_replayed["processed_event_ids"] == ["EV-DUP"]


def test_sequential_partial_refunds_complete_on_exact_total_and_block_over_refund():
    order = new_order("O1", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    # Step 1: First partial refund
    o1 = apply_order_event(order, event("r1", "refund_processed", amount_paise=400))
    assert o1["refunded_paise"] == 400
    assert o1["payment_status"] == "PAID"
    # Step 2: Second partial refund completing exact total
    o2 = apply_order_event(o1, event("r2", "refund_processed", amount_paise=600))
    assert o2["refunded_paise"] == 1000
    assert o2["payment_status"] == "REFUNDED"
    # Step 3: Third refund attempting over-refund is ignored
    o3 = apply_order_event(o2, event("r3", "refund_processed", amount_paise=100))
    assert o3["refunded_paise"] == 1000
    assert o3["payment_status"] == "REFUNDED"


def test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due():
    # Rejection before payment confirmation
    order_rej = new_order("O1", 2500, "PLACED")
    rej = apply_order_event(order_rej, event("e1", "restaurant_rejected"))
    assert rej["status"] == "REJECTED"
    assert rej["payment_status"] == "UNPAID"
    assert rej["refund_due_paise"] == 0
    # Late payment confirmation arrives
    paid_rej = apply_order_event(rej, event("e2", "payment_confirmed"))
    assert paid_rej["payment_status"] == "PAID"
    assert paid_rej["refund_due_paise"] == 2500
    # Eligible for refund
    refunded = apply_order_event(paid_rej, event("e3", "refund_processed", amount_paise=2500))
    assert refunded["refunded_paise"] == 2500
    assert refunded["payment_status"] == "REFUNDED"

    # Cancellation before payment confirmation
    order_canc = new_order("O2", 1500, "PLACED")
    canc = apply_order_event(order_canc, event("e4", "cancel_requested"))
    assert canc["status"] == "CANCELLED"
    assert canc["payment_status"] == "UNPAID"
    assert canc["refund_due_paise"] == 0
    paid_canc = apply_order_event(canc, event("e5", "payment_confirmed"))
    assert paid_canc["payment_status"] == "PAID"
    assert paid_canc["refund_due_paise"] == 1500


def test_boolean_and_non_integer_refund_amounts_rejected():
    order = new_order("O1", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    for invalid in [True, False, 100.0, "500", None, [100], {"amt": 100}]:
        out = apply_order_event(order, event(f"r-{invalid}", "refund_processed", amount_paise=invalid))
        assert out["refunded_paise"] == 0
        assert out["payment_status"] == "PAID"


def test_reconcile_handles_total_paise_and_simultaneous_amount_and_status_mismatch():
    internal = [new_order("ORD-1", 5000, "ACCEPTED")]
    provider = [{"order_id": "ORD-1", "amount_paise": 4500, "status": "CANCELLED"}]
    report = reconcile_orders(internal, provider)
    assert report["amount_mismatches"] == ["ORD-1"]
    assert report["status_mismatches"] == ["ORD-1"]
    assert report["matched"] == []
    assert report["missing_from_provider"] == []
    assert report["missing_from_internal"] == []


def test_malformed_and_missing_fields_do_not_corrupt_state():
    # None / non-dict order
    assert apply_order_event(None, event("e1", "payment_confirmed")) == {}
    assert apply_order_event("not-a-dict", event("e1", "payment_confirmed")) == {}

    # None / empty event
    order = new_order("O1", 1000)
    assert apply_order_event(order, None)["status"] == "PLACED"
    assert apply_order_event(order, {})["status"] == "PLACED"

    # Malformed processed_event_ids in order
    corrupt_order = {"order_id": "O1", "total_paise": 1000, "processed_event_ids": "corrupted"}
    res = apply_order_event(corrupt_order, event("e1", "payment_confirmed"))
    assert res["payment_status"] == "PAID"
    assert res["processed_event_ids"] == ["e1"]

    # Reconcile with None / malformed rows
    rec = reconcile_orders(None, [None, "invalid", {"order_id": ""}])
    assert rec["matched"] == []
    assert rec["missing_from_provider"] == []
    assert rec["missing_from_internal"] == []


def test_records_json_dataset_reconciliation_and_events_smoke():
    import json
    import os
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "records.json")
    with open(data_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # Reconcile entire dataset
    report = reconcile_orders(dataset["orders"], dataset["provider_records"])
    assert isinstance(report["matched"], list)
    assert isinstance(report["missing_from_provider"], list)
    assert isinstance(report["missing_from_internal"], list)
    assert isinstance(report["amount_mismatches"], list)
    assert isinstance(report["status_mismatches"], list)

    # Check deterministic sorting
    for k in ["matched", "missing_from_provider", "missing_from_internal", "amount_mismatches", "status_mismatches"]:
        assert report[k] == sorted(report[k], key=str)

    # Replay all events against orders dict
    orders_map = {o["order_id"]: dict(o) for o in dataset["orders"]}
    for ev_item in dataset["events"]:
        oid = ev_item.get("order_id") if isinstance(ev_item, dict) else None
        if oid and oid in orders_map:
            orders_map[oid] = apply_order_event(orders_map[oid], ev_item)
            assert orders_map[oid]["refunded_paise"] <= orders_map[oid]["refund_due_paise"]


def test_summarize_orders_by_state():
    from service import summarize_orders_by_state
    orders = [
        {"order_id": "O1", "status": "PLACED"},
        {"order_id": "O2", "status": "ACCEPTED"},
        {"order_id": "O3", "status": "PLACED"},
        {"order_id": "O4", "status": "DELIVERED"},
        None,
        "malformed",
        {"order_id": "O5"},
    ]
    summary = summarize_orders_by_state(orders)
    assert summary == {"ACCEPTED": 1, "DELIVERED": 1, "PLACED": 2}
    assert list(summary.keys()) == ["ACCEPTED", "DELIVERED", "PLACED"]
    assert summarize_orders_by_state(None) == {}
    assert summarize_orders_by_state([]) == {}
