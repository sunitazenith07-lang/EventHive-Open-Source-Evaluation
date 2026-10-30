import pytest

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
        assert out["processed_event_ids"]==[]


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


def test_missing_event_fields_do_not_mutate_order():
    order=new_order("O1",1000)
    malformed_events=[
        {"type":"payment_confirmed"},
        {"event_id":"e1"},
        {"event_id":"e2","type":[]},
        None,
        {"event_id":"e3","type":"payment_confirmed","order_id":"OTHER"},
        {"event_id":"e4","type":"payment_confirmed","order_id":None},
        {"event_id":"e5","type":"refund_processed"},
    ]
    for malformed in malformed_events:
        out=apply_order_event(order,malformed)
        assert out==order


def test_reconciliation_reports_amount_and_status_mismatches():
    report=reconcile_orders(
        [{"order_id":"A","amount_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":90,"status":"CANCELLED"}],
    )
    assert report["amount_mismatches"]==["A"]
    assert report["status_mismatches"]==["A"]
    assert report["matched"]==[]


def test_late_payment_confirmation_sets_refund_due_for_cancelled_order():
    order=new_order("O1",1000,"CANCELLED")
    out=apply_order_event(order,event("p1","payment_confirmed"))
    assert out["payment_status"]=="PAID"
    assert out["refund_due_paise"]==1000
    assert out["refunded_paise"]==0


def test_payment_confirmation_cannot_reverse_completed_refund():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="REFUNDED",refund_due_paise=1000,refunded_paise=1000)
    out=apply_order_event(order,event("p1","payment_confirmed"))
    assert out["payment_status"]=="REFUNDED"
    assert out["refunded_paise"]==1000


def test_conflicting_duplicate_event_id_is_ignored():
    order=new_order("O1",1000)
    first=apply_order_event(order,event("e1","payment_confirmed"))
    replay=apply_order_event(first,event("e1","restaurant_accepted"))
    assert replay["status"]=="PLACED"
    assert replay["payment_status"]=="PAID"
    assert replay["processed_event_ids"]==["e1"]


def test_reconciliation_does_not_match_records_missing_summary_fields():
    report=reconcile_orders(
        [{"order_id":"A","status":"PLACED"}],
        [{"order_id":"A","amount_paise":100}],
    )
    assert report["amount_mismatches"]==["A"]
    assert report["status_mismatches"]==["A"]
    assert report["matched"]==[]


@pytest.mark.parametrize("records", [
    [{"amount_paise":100,"status":"PLACED"}],
    [{"order_id":"A","amount_paise":100,"status":"PLACED"},
     {"order_id":"A","amount_paise":100,"status":"PLACED"}],
])
def test_reconciliation_rejects_missing_or_duplicate_order_ids(records):
    with pytest.raises(ValueError):
        reconcile_orders(records, [])


def test_refund_ignores_corrupt_refund_counters():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise="1000",refunded_paise=0)
    out=apply_order_event(order,event("r1","refund_processed",amount_paise=100))
    assert out["refunded_paise"]==0
    assert out["payment_status"]=="PAID"
    assert out["processed_event_ids"]==[]


def test_refund_above_outstanding_due_does_not_consume_event_id():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=1000,refunded_paise=900)
    out=apply_order_event(order,event("r1","refund_processed",amount_paise=200))
    assert out==order


@pytest.mark.parametrize("kind", ["restaurant_rejected","cancel_requested"])
@pytest.mark.parametrize("total", [None,-1,True,"100"])
def test_paid_rejection_or_cancellation_requires_valid_total(kind,total):
    order=new_order("O1",1000)
    if total is None:
        order.pop("total_paise")
    else:
        order["total_paise"]=total
    order["payment_status"]="PAID"
    out=apply_order_event(order,event("e1",kind))
    assert out==order


def test_late_payment_on_cancelled_order_requires_valid_total():
    order=new_order("O1",1000,"CANCELLED")
    order.pop("total_paise")
    out=apply_order_event(order,event("p1","payment_confirmed"))
    assert out==order


@pytest.mark.parametrize("amount,status", [(True,"PLACED"),(100,[])])
def test_reconciliation_does_not_match_invalid_summary_values(amount,status):
    report=reconcile_orders(
        [{"order_id":"A","amount_paise":amount,"status":status}],
        [{"order_id":"A","amount_paise":amount,"status":status}],
    )
    assert report["matched"]==[]
    assert report["amount_mismatches"]==(["A"] if type(amount) is not int else [])
    assert report["status_mismatches"]==(["A"] if not isinstance(status,str) or not status else [])


def test_reconciliation_uses_order_total_for_internal_orders():
    report=reconcile_orders(
        [{"order_id":"A","total_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":100,"status":"PLACED"}],
    )
    assert report["matched"]==["A"]
    assert report["amount_mismatches"]==[]


def test_demo_reconciliation_matches_equal_order_total_and_amount():
    from fixtures import sample_orders, sample_provider_orders

    report=reconcile_orders(sample_orders(),sample_provider_orders())
    assert report["matched"]==["ORD-101"]
    assert report["amount_mismatches"]==[]
    assert report["status_mismatches"]==["ORD-102"]


def test_explicit_malformed_amount_does_not_fall_back_to_order_total():
    report=reconcile_orders(
        [{"order_id":"A","amount_paise":None,"total_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":100,"status":"PLACED"}],
    )
    assert report["matched"]==[]
    assert report["amount_mismatches"]==["A"]
