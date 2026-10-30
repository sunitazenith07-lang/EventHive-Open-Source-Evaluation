"""Starter order lifecycle and refund service; all data is synthetic."""
import csv
import io
from copy import deepcopy

REFUNDABLE_STATUSES=("CANCELLED","REJECTED")


def _valid_id(value) -> bool:
    """IDs are non-blank strings or ints. Checked by type, not truthiness:
    0 is falsy but valid, and unhashable values such as lists cannot be dict keys."""
    if isinstance(value,str):
        return value.strip()!=""
    return isinstance(value,int) and not isinstance(value,bool)


def _refund_allowed(order: dict, amount) -> bool:
    """A refund needs a paid cancelled/rejected order and a positive integer
    amount that fits in the outstanding refund due."""
    # bool is a subclass of int, so True would otherwise count as 1 paise.
    if not isinstance(amount,int) or isinstance(amount,bool) or amount<=0:
        return False
    if order.get("status") not in REFUNDABLE_STATUSES or order["payment_status"]!="PAID":
        return False
    outstanding=order["refund_due_paise"]-order["refunded_paise"]
    return amount<=outstanding


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out=deepcopy(order)
    out.setdefault("payment_status","UNPAID")
    out.setdefault("refund_due_paise",0)
    out.setdefault("refunded_paise",0)
    out.setdefault("processed_event_ids",[])
    if not isinstance(event,dict):
        return out
    event_id=event.get("event_id")
    kind=event.get("type")

    # Without a usable event_id a replay cannot be detected, so the event is ignored.
    if not _valid_id(event_id) or event_id in out["processed_event_ids"]:
        return out

    if kind=="payment_confirmed" and out["payment_status"]=="UNPAID":
        out["payment_status"]="PAID"
        # Payment that lands after a cancel/reject is owed back in full.
        if out.get("status") in REFUNDABLE_STATUSES:
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="restaurant_accepted" and out.get("status")=="PLACED":
        out["status"]="ACCEPTED"
    elif kind=="restaurant_rejected" and out.get("status")=="PLACED":
        out["status"]="REJECTED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="cancel_requested" and out.get("status") in ("PLACED","ACCEPTED"):
        out["status"]="CANCELLED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="dispatch_started" and out.get("status")=="ACCEPTED":
        out["status"]="OUT_FOR_DELIVERY"
    elif kind=="order_delivered" and out.get("status")=="OUT_FOR_DELIVERY":
        out["status"]="DELIVERED"
    elif kind=="refund_processed" and _refund_allowed(out,event.get("amount_paise")):
        out["refunded_paise"] += event["amount_paise"]
        if out["refunded_paise"]==out["refund_due_paise"]:
            out["payment_status"]="REFUNDED"

    out["processed_event_ids"].append(event_id)
    return out


def apply_events(orders: list[dict], events: list[dict]) -> tuple[dict, dict]:
    """Apply events in order, routing each by its order_id.

    Returns copies of the updated orders keyed by order_id, and a report of what
    was skipped: invalid_orders (positions of orders with no usable order_id),
    duplicate_order_ids (listed more than once, so none of them is processed),
    unrouted_events (order_id missing, unknown or duplicated) and
    cross_order_duplicates (event_id already processed by a different order).
    """
    keyed,invalid,dupes=_index_rows(orders)
    # Copies, so changing the result never changes the caller's orders.
    by_id={oid:deepcopy(o) for oid,o in keyed.items() if oid not in dupes}
    # processed_event_ids is per order, but an event_id names one event overall,
    # so the same ID arriving for a different order is not applied again.
    used_by={eid:oid for oid,o in by_id.items()
             for eid in o.get("processed_event_ids",[]) if _valid_id(eid)}
    skipped={"invalid_orders":invalid,"duplicate_order_ids":sorted(dupes,key=str),
             "unrouted_events":[],"cross_order_duplicates":[]}
    for i,e in enumerate(events):
        oid=e.get("order_id") if isinstance(e,dict) else None
        if not (_valid_id(oid) and oid in by_id):
            skipped["unrouted_events"].append(i)
            continue
        eid=e.get("event_id")
        if _valid_id(eid):
            if used_by.get(eid,oid)!=oid:
                skipped["cross_order_duplicates"].append(i)
                continue
            used_by[eid]=oid
        by_id[oid]=apply_order_event(by_id[oid],e)
    return by_id,skipped


AWAITING_REFUND_COLUMNS=["order_id","status","refund_due_paise","refunded_paise","outstanding_paise"]


def awaiting_refund_csv(orders) -> str:
    """CSV of orders that still owe the customer money, sorted by order_id."""
    buf=io.StringIO()
    writer=csv.writer(buf,lineterminator="\n")
    writer.writerow(AWAITING_REFUND_COLUMNS)
    for o in sorted(orders,key=lambda o:str(o.get("order_id"))):
        due,paid=o.get("refund_due_paise",0),o.get("refunded_paise",0)
        if due>paid:
            writer.writerow([o.get("order_id"),o.get("status"),due,paid,due-paid])
    return buf.getvalue()


def _amount(record: dict):
    """Provider rows use amount_paise; internal orders (new_order) use total_paise."""
    return record["amount_paise"] if "amount_paise" in record else record.get("total_paise")


def _index_rows(rows: list) -> tuple[dict, list[int], set]:
    """Key rows by order_id; return the positions of rows that have no usable ID
    and the IDs that appear more than once."""
    keyed,invalid,dupes={},[],set()
    for i,r in enumerate(rows):
        if not (isinstance(r,dict) and _valid_id(r.get("order_id"))):
            invalid.append(i)
        elif r["order_id"] in keyed:
            dupes.add(r["order_id"])
        else:
            keyed[r["order_id"]]=r
    return keyed,invalid,dupes


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left,bad_left,dup_left=_index_rows(internal)
    right,bad_right,dup_right=_index_rows(provider)
    # Which copy of a duplicated ID is correct is unknown, so it is not compared.
    dupes=dup_left|dup_right
    report={"matched":[],"missing_from_provider":[],"missing_from_internal":[],
            "amount_mismatches":[],"status_mismatches":[],
            "duplicate_order_ids":sorted(dupes,key=str),
            "invalid_internal_rows":bad_left,"invalid_provider_rows":bad_right}
    for key in sorted((set(left)|set(right))-dupes,key=lambda x:str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a,b=left[key],right[key]
            amount_ok=_amount(a)==_amount(b)
            status_ok=a.get("status")==b.get("status")
            # An order can differ in both ways; each is reported separately.
            if not amount_ok:
                report["amount_mismatches"].append(key)
            if not status_ok:
                report["status_mismatches"].append(key)
            if amount_ok and status_ok:
                report["matched"].append(key)
    return report
