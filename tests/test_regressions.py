"""Regression tests for defects fixed in service.py."""
from models import new_order
from service import apply_order_event


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
