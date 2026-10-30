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


def test_late_payment_confirmed_on_rejected_order():
    order = new_order("O1", 1000)
    rejected = apply_order_event(order, event("e1", "restaurant_rejected"))
    assert rejected["status"] == "REJECTED"
    assert rejected["payment_status"] == "UNPAID"
    assert rejected["refund_due_paise"] == 0

    paid = apply_order_event(rejected, event("e2", "payment_confirmed"))
    assert paid["status"] == "REJECTED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 1000


def test_late_payment_confirmed_on_cancelled_order():
    order = new_order("O2", 2500)
    cancelled = apply_order_event(order, event("e1", "cancel_requested"))
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["payment_status"] == "UNPAID"
    assert cancelled["refund_due_paise"] == 0

    paid = apply_order_event(cancelled, event("e2", "payment_confirmed"))
    assert paid["status"] == "CANCELLED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 2500


def test_reconcile_both_amount_and_status_mismatch():
    report = reconcile_orders(
        [{"order_id": "A", "amount_paise": 1000, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 800, "status": "CANCELLED"}]
    )
    assert report["amount_mismatches"] == ["A"]
    assert report["status_mismatches"] == ["A"]
    assert report["matched"] == []


def test_reconcile_supports_total_paise_internal_orders():
    report = reconcile_orders(
        [new_order("ORD-101", 45900, "PLACED")],
        [{"order_id": "ORD-101", "amount_paise": 45900, "status": "PLACED"}]
    )
    assert report["matched"] == ["ORD-101"]
    assert report["amount_mismatches"] == []
    assert report["status_mismatches"] == []


def test_refund_boolean_type_ignored():
    order = new_order("O1", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    out_true = apply_order_event(order, event("r1", "refund_processed", amount_paise=True))
    assert out_true["refunded_paise"] == 0
    out_false = apply_order_event(order, event("r2", "refund_processed", amount_paise=False))
    assert out_false["refunded_paise"] == 0


def test_two_step_partial_refund_to_full_refund():
    order = new_order("O1", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)

    part1 = apply_order_event(order, event("r1", "refund_processed", amount_paise=400))
    assert part1["refunded_paise"] == 400
    assert part1["payment_status"] == "PAID"

    part2 = apply_order_event(part1, event("r2", "refund_processed", amount_paise=600))
    assert part2["refunded_paise"] == 1000
    assert part2["payment_status"] == "REFUNDED"


def test_replayed_refund_event_does_not_double_refund():
    order = new_order("O1", 1000, "CANCELLED")
    order.update(payment_status="PAID", refund_due_paise=1000)
    e = event("r1", "refund_processed", amount_paise=500)
    once = apply_order_event(order, e)
    assert once["refunded_paise"] == 500

    twice = apply_order_event(once, e)
    assert twice["refunded_paise"] == 500
    assert twice["processed_event_ids"] == ["r1"]


def test_malformed_event_and_order_inputs():
    assert apply_order_event(None, event("e1", "payment_confirmed")) == {}
    order = new_order("O1", 1000)
    assert apply_order_event(order, None) == order
    assert apply_order_event(order, "not-a-dict") == order
