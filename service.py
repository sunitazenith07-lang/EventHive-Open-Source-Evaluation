"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy

REFUNDABLE_STATUSES=("CANCELLED","REJECTED")


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
    event_id=event.get("event_id")
    kind=event.get("type")

    # Without an event_id a replay cannot be detected, so the event is ignored.
    if not event_id or event_id in out["processed_event_ids"]:
        return out

    # Deliberate starter defects: duplicate and invalid refund events are not
    # fully protected, and some transitions need tighter validation.
    if kind=="payment_confirmed":
        out["payment_status"]="PAID"
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


def _amount(record: dict):
    """Provider rows use amount_paise; internal orders (new_order) use total_paise."""
    return record["amount_paise"] if "amount_paise" in record else record.get("total_paise")


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left={r.get("order_id"):r for r in internal}
    right={r.get("order_id"):r for r in provider}
    report={"matched":[],"missing_from_provider":[],"missing_from_internal":[],
            "amount_mismatches":[],"status_mismatches":[]}
    for key in sorted(set(left)|set(right),key=lambda x:str(x)):
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
