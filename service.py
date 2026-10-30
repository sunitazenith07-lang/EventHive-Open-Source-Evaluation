"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out=deepcopy(order)
    out.setdefault("payment_status","UNPAID")
    out.setdefault("refund_due_paise",0)
    out.setdefault("refunded_paise",0)
    processed_event_ids=out.get("processed_event_ids")
    if not isinstance(processed_event_ids,list):
        processed_event_ids=[]
        out["processed_event_ids"]=processed_event_ids
    if not isinstance(event,dict):
        return out
    event_id=event.get("event_id")
    kind=event.get("type")

    valid_kinds={"payment_confirmed","restaurant_accepted","restaurant_rejected",
                 "cancel_requested","dispatch_started","order_delivered",
                 "refund_processed"}
    if (not isinstance(event_id,str) or not event_id
            or event_id in processed_event_ids
            or not isinstance(kind,str) or kind not in valid_kinds):
        return out

    if kind=="payment_confirmed":
        out["payment_status"]="PAID"
        if out.get("status") in ("CANCELLED","REJECTED"):
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
    elif kind=="refund_processed":
        amount=event.get("amount_paise")
        due=out.get("refund_due_paise",0)
        refunded=out.get("refunded_paise",0)
        if (out.get("status") in ("CANCELLED","REJECTED")
                and out.get("payment_status")=="PAID"
                and type(amount) is int and amount>0
                and type(due) is int and due>0
                and type(refunded) is int and 0<=refunded<=due
                and amount<=due-refunded):
            out["refunded_paise"] += amount
            if out["refunded_paise"] == due:
                out["payment_status"]="REFUNDED"

    processed_event_ids.append(event_id)
    return out


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
            amount_mismatch=a.get("amount_paise") != b.get("amount_paise")
            status_mismatch=a.get("status") != b.get("status")
            if amount_mismatch:
                report["amount_mismatches"].append(key)
            if status_mismatch:
                report["status_mismatches"].append(key)
            if not amount_mismatch and not status_mismatch:
                report["matched"].append(key)
    return report
