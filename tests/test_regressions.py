"""Regression tests for defects fixed in service.py."""
import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def event(event_id, kind, **extra):
    return {"event_id":event_id,"type":kind,**extra}


def refundable_order(total=1000):
    order=new_order("O1",total,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=total)
    return order


# Bug 1: idempotency

def test_replayed_refund_is_not_applied_twice():
    order=refundable_order()
    e=event("r1","refund_processed",amount_paise=400)
    once=apply_order_event(order,e)
    twice=apply_order_event(once,e)
    assert twice["refunded_paise"]==400
    assert twice["processed_event_ids"]==["r1"]


def test_replayed_id_with_conflicting_payload_is_ignored():
    order=refundable_order()
    once=apply_order_event(order,event("r1","refund_processed",amount_paise=400))
    twice=apply_order_event(once,event("r1","refund_processed",amount_paise=600))
    assert twice["refunded_paise"]==400


def test_event_without_id_is_ignored():
    order=new_order("O1",1000)
    for e in [{"type":"payment_confirmed"},event(None,"payment_confirmed"),event("","payment_confirmed")]:
        out=apply_order_event(order,e)
        assert out["payment_status"]=="UNPAID"
        assert out["processed_event_ids"]==[]


# Bug 2: refund validation

def test_partial_then_final_refund_marks_refunded():
    order=refundable_order()
    order=apply_order_event(order,event("r1","refund_processed",amount_paise=400))
    assert order["payment_status"]=="PAID"
    order=apply_order_event(order,event("r2","refund_processed",amount_paise=600))
    assert order["refunded_paise"]==1000
    assert order["payment_status"]=="REFUNDED"


def test_refund_after_full_refund_is_rejected():
    order=apply_order_event(refundable_order(),event("r1","refund_processed",amount_paise=1000))
    out=apply_order_event(order,event("r2","refund_processed",amount_paise=1))
    assert out["refunded_paise"]==1000


def test_refund_without_amount_is_rejected():
    out=apply_order_event(refundable_order(),event("r1","refund_processed"))
    assert out["refunded_paise"]==0
    assert out["payment_status"]=="PAID"


def test_rejected_refund_id_is_still_recorded():
    out=apply_order_event(refundable_order(),event("r1","refund_processed",amount_paise=-5))
    assert out["processed_event_ids"]==["r1"]


def test_full_paid_rejection_lifecycle():
    order=new_order("O1",2500)
    for e in [event("p1","payment_confirmed"),event("x1","restaurant_rejected"),
              event("r1","refund_processed",amount_paise=1000),
              event("r2","refund_processed",amount_paise=1500)]:
        order=apply_order_event(order,e)
    assert order["status"]=="REJECTED"
    assert order["refund_due_paise"]==2500
    assert order["refunded_paise"]==2500
    assert order["payment_status"]=="REFUNDED"


# Bug 3: status mismatches in reconciliation

def test_amount_and_status_mismatch_reported_in_both_lists():
    report=reconcile_orders([{"order_id":"A","amount_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":90,"status":"CANCELLED"}])
    assert report["amount_mismatches"]==["A"]
    assert report["status_mismatches"]==["A"]
    assert report["matched"]==[]


def test_status_mismatches_are_sorted():
    internal=[{"order_id":oid,"amount_paise":1,"status":"PLACED"} for oid in ["C","A","B"]]
    provider=[{"order_id":oid,"amount_paise":1,"status":"DELIVERED"} for oid in ["B","C","A"]]
    assert reconcile_orders(internal,provider)["status_mismatches"]==["A","B","C"]


# Bug 4: internal orders store their amount as total_paise

def test_internal_total_paise_is_compared_with_provider_amount():
    report=reconcile_orders([new_order("A",45900)],
        [{"order_id":"A","amount_paise":45900,"status":"PLACED"}])
    assert report["matched"]==["A"]
    assert report["amount_mismatches"]==[]


def test_internal_total_paise_mismatch_is_reported():
    report=reconcile_orders([new_order("A",45900)],
        [{"order_id":"A","amount_paise":45000,"status":"PLACED"}])
    assert report["amount_mismatches"]==["A"]


# Bug 5: payment_confirmed was accepted in any payment state

def test_payment_after_full_refund_does_not_reset_status():
    order=apply_order_event(refundable_order(),event("r1","refund_processed",amount_paise=1000))
    out=apply_order_event(order,event("p2","payment_confirmed"))
    assert out["payment_status"]=="REFUNDED"


def test_payment_after_cancellation_creates_refund_due():
    order=apply_order_event(new_order("O1",1000),event("c1","cancel_requested"))
    assert order["refund_due_paise"]==0
    out=apply_order_event(order,event("p1","payment_confirmed"))
    assert out["payment_status"]=="PAID"
    assert out["refund_due_paise"]==1000


# QoL 1: malformed events


@pytest.mark.parametrize("bad",[None,"payment_confirmed",[],42])
def test_non_dict_event_is_ignored(bad):
    order=new_order("O1",1000)
    out=apply_order_event(order,bad)
    assert out["payment_status"]=="UNPAID"
    assert out["processed_event_ids"]==[]


# QoL 2: malformed reconciliation rows

def test_rows_without_order_id_are_reported_not_merged():
    internal=[{"amount_paise":1,"status":"PLACED"},None,
              {"order_id":"A","amount_paise":5,"status":"PLACED"},{"order_id":"","amount_paise":2}]
    provider=[{"order_id":"A","amount_paise":5,"status":"PLACED"},"junk"]
    report=reconcile_orders(internal,provider)
    assert report["matched"]==["A"]
    assert report["missing_from_provider"]==[]
    assert report["invalid_internal_rows"]==[0,1,3]
    assert report["invalid_provider_rows"]==[1]
