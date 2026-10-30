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


def test_duplicate_refund_event_is_idempotent():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=1000)
    refund=event("r1","refund_processed",amount_paise=400)
    first=apply_order_event(order,refund)
    second=apply_order_event(first,refund)
    assert second["refunded_paise"]==400
    assert second["payment_status"]=="PAID"
    assert second["processed_event_ids"]==["r1"]


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


def test_paid_rejection_partial_then_full_refund_flow():
    order=new_order("O1",1000)
    for current_event in [
        event("e1","payment_confirmed"),
        event("e2","restaurant_rejected"),
        event("r1","refund_processed",amount_paise=400),
        event("r2","refund_processed",amount_paise=600),
    ]:
        order=apply_order_event(order,current_event)

    assert order["status"]=="REJECTED"
    assert order["payment_status"]=="REFUNDED"
    assert order["refund_due_paise"]==1000
    assert order["refunded_paise"]==1000


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


def test_reconcile_reports_amount_and_status_differences_separately():
    report=reconcile_orders(
        [{"order_id":"A","amount_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":90,"status":"CANCELLED"}],
    )
    assert report["amount_mismatches"]==["A"]
    assert report["status_mismatches"]==["A"]
    assert report["matched"]==[]


def test_empty_reconciliation():
    assert all(v==[] for v in reconcile_orders([],[]).values())


def test_payment_confirmed_after_cancellation_marks_refund_due():
    order = new_order("O1", 1500)
    order = apply_order_event(order, event("e1", "cancel_requested"))
    assert order["status"] == "CANCELLED"
    assert order["payment_status"] == "UNPAID"
    assert order["refund_due_paise"] == 0

    order = apply_order_event(order, event("e2", "payment_confirmed"))
    assert order["status"] == "CANCELLED"
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 1500

    order = apply_order_event(order, event("r1", "refund_processed", amount_paise=1500))
    assert order["payment_status"] == "REFUNDED"
    assert order["refunded_paise"] == 1500


def test_payment_confirmed_after_rejection_marks_refund_due():
    order = new_order("O2", 2000)
    order = apply_order_event(order, event("e1", "restaurant_rejected"))
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "UNPAID"
    assert order["refund_due_paise"] == 0

    order = apply_order_event(order, event("e2", "payment_confirmed"))
    assert order["status"] == "REJECTED"
    assert order["payment_status"] == "PAID"
    assert order["refund_due_paise"] == 2000
