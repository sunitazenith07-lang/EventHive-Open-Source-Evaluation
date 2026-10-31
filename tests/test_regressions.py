"""Regression tests for defects fixed in service.py."""
from copy import deepcopy

import pytest
from models import new_order
from service import apply_events, apply_order_event, awaiting_refund_csv, reconcile_orders


def event(event_id, kind, **extra):
    return {"event_id":event_id,"type":kind,**extra}


def refundable_order(total=1000,order_id="O1"):
    order=new_order(order_id,total,"CANCELLED")
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


# QoL 3: duplicate order IDs

def test_duplicate_order_id_is_reported_not_matched():
    internal=[{"order_id":"A","amount_paise":1,"status":"PLACED"},
              {"order_id":"A","amount_paise":2,"status":"PLACED"},
              {"order_id":"B","amount_paise":3,"status":"PLACED"}]
    provider=[{"order_id":"A","amount_paise":2,"status":"PLACED"},
              {"order_id":"B","amount_paise":3,"status":"PLACED"},
              {"order_id":"C","amount_paise":4,"status":"PLACED"},
              {"order_id":"C","amount_paise":4,"status":"PLACED"}]
    report=reconcile_orders(internal,provider)
    assert report["duplicate_order_ids"]==["A","C"]
    assert report["matched"]==["B"]
    assert report["missing_from_internal"]==[]


# QoL 4: batch event processing

def test_apply_events_routes_by_order_id_and_reports_unknown():
    orders=[new_order("A",1000),new_order("B",500)]
    events=[{"event_id":"1","order_id":"A","type":"payment_confirmed"},
            {"event_id":"2","order_id":"B","type":"restaurant_accepted"},
            {"event_id":"3","order_id":"Z","type":"payment_confirmed"},
            {"event_id":"4","type":"payment_confirmed"},
            None,
            {"event_id":"5","order_id":"A","type":"restaurant_rejected"},
            {"event_id":"5","order_id":"A","type":"restaurant_rejected"}]
    result,skipped=apply_events(orders,events)
    assert skipped["unrouted_events"]==[2,3,4]
    assert skipped["cross_order_duplicates"]==[]
    assert result["A"]["status"]=="REJECTED"
    assert result["A"]["refund_due_paise"]==1000
    assert result["A"]["processed_event_ids"]==["1","5"]
    assert result["B"]["status"]=="ACCEPTED"
    assert orders[0]["status"]=="PLACED"


def test_dataset_refunds_never_exceed_due():
    import json
    from pathlib import Path
    data=json.loads((Path(__file__).parent.parent/"data"/"records.json").read_text(encoding="utf-8"))
    result,_=apply_events(data["orders"],data["events"])
    for o in result.values():
        assert 0<=o["refunded_paise"]<=o["refund_due_paise"]


# Stretch: awaiting-refund CSV

def test_awaiting_refund_csv_lists_only_outstanding_orders_sorted():
    partial=refundable_order(1000)
    partial.update(order_id="B",refunded_paise=400)
    full=refundable_order(500)
    full.update(order_id="A",refunded_paise=500,payment_status="REFUNDED")
    owed=refundable_order(300)
    owed["order_id"]="C"
    lines=awaiting_refund_csv([owed,new_order("D",100),partial,full]).splitlines()
    assert lines==["order_id,status,refund_due_paise,refunded_paise,outstanding_paise",
                   "B,CANCELLED,1000,400,600",
                   "C,CANCELLED,300,0,300"]


def test_awaiting_refund_csv_empty_input_has_header_only():
    assert awaiting_refund_csv([])=="order_id,status,refund_due_paise,refunded_paise,outstanding_paise\n"


# Follow-up 1: test_input_order_is_not_mutated compares against dict(order),
# which shares processed_event_ids, so it cannot see that list being changed.

@pytest.mark.parametrize("kind",["payment_confirmed","restaurant_accepted","restaurant_rejected",
    "cancel_requested","dispatch_started","order_delivered","refund_processed"])
def test_input_order_and_nested_event_list_are_not_mutated(kind):
    order=refundable_order() if kind=="refund_processed" else new_order("O1",1000)
    order["processed_event_ids"]=["earlier"]
    before=deepcopy(order)
    apply_order_event(order,event("e1",kind,amount_paise=100))
    assert order==before


# Follow-up 2: IDs were checked by truthiness, so 0 counted as missing, and
# unhashable IDs such as lists crashed the dict lookups.

@pytest.mark.parametrize("event_id",[0,7,"e1"])
def test_valid_event_ids_including_zero_are_applied(event_id):
    out=apply_order_event(new_order("O1",1000),event(event_id,"payment_confirmed"))
    assert out["payment_status"]=="PAID"
    assert out["processed_event_ids"]==[event_id]


@pytest.mark.parametrize("event_id",[None,""," ",True,False,1.5,[],["e1"],{}])
def test_unusable_event_ids_are_ignored(event_id):
    out=apply_order_event(new_order("O1",1000),event(event_id,"payment_confirmed"))
    assert out["payment_status"]=="UNPAID"
    assert out["processed_event_ids"]==[]


def test_order_id_zero_is_reconciled():
    rows=[{"order_id":0,"amount_paise":1,"status":"PLACED"}]
    report=reconcile_orders(rows,rows)
    assert report["matched"]==[0]
    assert report["invalid_internal_rows"]==[]


def test_unhashable_order_ids_in_reconciliation_are_reported():
    report=reconcile_orders([{"order_id":["A"],"amount_paise":1},{"order_id":{"x":1}}],
                            [{"order_id":["A"],"amount_paise":1}])
    assert report["invalid_internal_rows"]==[0,1]
    assert report["invalid_provider_rows"]==[0]


def test_unhashable_event_order_id_is_unrouted():
    result,skipped=apply_events([new_order("A",1000)],
        [{"event_id":"e1","order_id":["A"],"type":"payment_confirmed"}])
    assert skipped["unrouted_events"]==[0]
    assert result["A"]["payment_status"]=="UNPAID"


# Follow-up 3: processed_event_ids is kept per order, so one event_id sent to
# two different orders was applied to both (a double refund).

def test_event_id_reused_on_another_order_is_skipped():
    refund={"event_id":"R-1","type":"refund_processed","amount_paise":500}
    result,skipped=apply_events([refundable_order(500,"X"),refundable_order(500,"Y")],
                                [{**refund,"order_id":"X"},{**refund,"order_id":"Y"}])
    assert result["X"]["refunded_paise"]==500
    assert result["Y"]["refunded_paise"]==0
    assert skipped["cross_order_duplicates"]==[1]


def test_event_id_processed_by_another_order_before_the_batch_is_skipped():
    x=refundable_order(500,"X")
    x["processed_event_ids"]=["R-1"]
    result,skipped=apply_events([x,refundable_order(500,"Y")],
        [{"event_id":"R-1","order_id":"Y","type":"refund_processed","amount_paise":500}])
    assert result["Y"]["refunded_paise"]==0
    assert skipped["cross_order_duplicates"]==[0]


def test_same_order_replay_is_not_reported_as_cross_order():
    refund={"event_id":"R-1","order_id":"X","type":"refund_processed","amount_paise":200}
    result,skipped=apply_events([refundable_order(500,"X")],[refund,refund])
    assert result["X"]["refunded_paise"]==200
    assert skipped["cross_order_duplicates"]==[]


# Follow-up 4: apply_events crashed on an order without an order_id, silently
# used the last of two orders sharing an ID, and returned untouched orders as
# the caller's own objects.

def test_apply_events_reports_orders_without_usable_id():
    orders=[{"total_paise":5},None,new_order("A",1000),{"order_id":["B"]}]
    result,skipped=apply_events(orders,[{"event_id":"e1","order_id":"A","type":"payment_confirmed"}])
    assert list(result)==["A"]
    assert result["A"]["payment_status"]=="PAID"
    assert skipped["invalid_orders"]==[0,1,3]


def test_apply_events_does_not_guess_between_duplicate_orders():
    orders=[new_order("A",1),new_order("A",2),new_order("B",3)]
    result,skipped=apply_events(orders,[{"event_id":"e1","order_id":"A","type":"payment_confirmed"}])
    assert list(result)==["B"]
    assert skipped["duplicate_order_ids"]==["A"]
    assert skipped["unrouted_events"]==[0]


def test_apply_events_returns_copies_not_the_callers_orders():
    orders=[new_order("A",1000)]
    result,_=apply_events(orders,[])
    assert result["A"] is not orders[0]
    result["A"]["status"]="DELIVERED"
    assert orders[0]["status"]=="PLACED"


# Follow-up 5: a null or text amount stored on the order crashed the refund
# check and the CSV report with TypeError.

@pytest.mark.parametrize("field,value",[("refund_due_paise",None),("refunded_paise",None),
    ("refund_due_paise","1000"),("refunded_paise",1.5)])
def test_refund_on_order_with_broken_amounts_is_ignored(field,value):
    order=refundable_order()
    order[field]=value
    out=apply_order_event(order,event("r1","refund_processed",amount_paise=100))
    assert out[field]==value
    assert out["payment_status"]=="PAID"


def test_null_total_does_not_become_the_refund_due():
    order=new_order("O1",None)
    order["payment_status"]="PAID"
    out=apply_order_event(order,event("x1","restaurant_rejected"))
    assert out["status"]=="REJECTED"
    assert out["refund_due_paise"]==0
    out=apply_order_event(out,event("r1","refund_processed",amount_paise=100))
    assert out["refunded_paise"]==0


def test_awaiting_refund_csv_skips_rows_with_broken_amounts():
    broken=refundable_order(1000,"A")
    broken["refund_due_paise"]=None
    lines=awaiting_refund_csv([broken,refundable_order(300,"B")]).splitlines()
    assert lines[1:]==["B,CANCELLED,300,0,300"]


# Follow-up 6: processed_event_ids that was null or not a list crashed, and a
# text value was searched as a string ("E1" was found inside "E12").

def test_null_event_history_counts_as_empty():
    order=new_order("O1",1000)
    order["processed_event_ids"]=None
    out=apply_order_event(order,event("p1","payment_confirmed"))
    assert out["payment_status"]=="PAID"
    assert out["processed_event_ids"]==["p1"]


def test_tuple_event_history_is_used_as_a_list():
    order=new_order("O1",1000)
    order["processed_event_ids"]=("p1",)
    assert apply_order_event(order,event("p1","payment_confirmed"))["payment_status"]=="UNPAID"
    out=apply_order_event(order,event("p2","payment_confirmed"))
    assert out["processed_event_ids"]==["p1","p2"]


@pytest.mark.parametrize("history",["E12",5,{"E1":1}])
def test_unreadable_event_history_means_events_are_ignored(history):
    order=new_order("O1",1000)
    order["processed_event_ids"]=history
    out=apply_order_event(order,event("E99","payment_confirmed"))
    assert out["payment_status"]=="UNPAID"
    assert out["processed_event_ids"]==history


def test_apply_events_with_null_event_history():
    order=new_order("O1",1000)
    order["processed_event_ids"]=None
    result,_=apply_events([order],[{"event_id":"p1","order_id":"O1","type":"payment_confirmed"}])
    assert result["O1"]["payment_status"]=="PAID"


# Follow-up 7: calling apply_order_event directly with something that is not
# an order crashed with AttributeError on setdefault.

@pytest.mark.parametrize("bad",[None,"O1",[],42])
def test_non_dict_order_is_returned_unchanged(bad):
    assert apply_order_event(bad,event("p1","payment_confirmed"))==bad


# Follow-up 8: None instead of a list crashed apply_events, reconcile_orders
# and awaiting_refund_csv with TypeError, although an empty list worked.

def test_apply_events_treats_none_as_no_rows():
    result,skipped=apply_events(None,None)
    assert result=={}
    assert all(v==[] for v in skipped.values())
    kept,_=apply_events([new_order("A",1000)],None)
    assert kept["A"]["status"]=="PLACED"


def test_reconcile_orders_treats_none_as_no_rows():
    assert all(v==[] for v in reconcile_orders(None,None).values())
    assert reconcile_orders([new_order("A",1000)],None)["missing_from_provider"]==["A"]


def test_awaiting_refund_csv_treats_none_as_no_rows():
    assert awaiting_refund_csv(None)=="order_id,status,refund_due_paise,refunded_paise,outstanding_paise\n"


# Follow-up 9: the dict returned by apply_events could not be passed straight
# on: the CSV crashed on its keys, apply_events and reconcile_orders treated
# every order as invalid, and a non-dict row crashed the CSV.

def test_awaiting_refund_csv_accepts_the_apply_events_result():
    result,_=apply_events([refundable_order(300,"A")],[])
    assert awaiting_refund_csv(result).splitlines()[1:]==["A,CANCELLED,300,0,300"]


def test_apply_events_and_reconcile_accept_the_apply_events_result():
    result,_=apply_events([refundable_order(300,"A")],[])
    again,skipped=apply_events(result,[{"event_id":"r1","order_id":"A","type":"refund_processed","amount_paise":300}])
    assert skipped["invalid_orders"]==[]
    assert again["A"]["payment_status"]=="REFUNDED"
    assert reconcile_orders(result,[{"order_id":"A","amount_paise":300,"status":"CANCELLED"}])["matched"]==["A"]


def test_awaiting_refund_csv_skips_rows_that_are_not_orders():
    lines=awaiting_refund_csv([None,"junk",refundable_order(300,"A")]).splitlines()
    assert lines[1:]==["A,CANCELLED,300,0,300"]
