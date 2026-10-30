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
    out.setdefault("processed_event_ids",[])
    event_id=event.get("event_id")
    kind=event.get("type")
    if event_id in out["processed_event_ids"]:
        return out
    status = out.get("status", "PLACED")
    payment_status = out.get("payment_status", "UNPAID")    
    # Deliberate starter defects: duplicate and invalid refund events are not
    # fully protected, and some transitions need tighter validation.
    if kind=="payment_confirmed":
        if payment_status == "UNPAID":
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
        
    elif kind=="refund_processed":
        # Bug to find: validate eligibility, positive amount and maximum refund.
        amount_paise = event.get("amount_paise", 0)
        outstanding = out["refund_due_paise"] - out["refunded_paise"]
        if (
            out.get("status") in ("CANCELLED", "REJECTED")
            and out["payment_status"] == "PAID"
            and isinstance(amount_paise, int)
            and not isinstance(amount_paise, bool)
            and 0 < amount_paise <= outstanding
        ):
            out["refunded_paise"] += amount_paise
        if out["refund_due_paise"] > 0 and out["refunded_paise"] >= out["refund_due_paise"]:
            out["payment_status"]="REFUNDED"
    if event_id:
        out["processed_event_ids"].append(event_id)
    return out
        


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left={r.get("order_id"):r for r in internal}
    right={r.get("order_id"):r for r in provider}
    report={"matched":[],"missing_from_provider":[],"missing_from_internal":[],
            "amount_mismatches":[],"status_mismatches":[]}
    all_keys = sorted(set(left) | set(right), key=lambda x: str(x))
    for key in all_keys:
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a,b=left[key],right[key]
            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)
            # Deliberate starter defect: mismatched statuses may be called matched.
            else:
                a, b = left[key], right[key]
            
            
                amt_a = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
                amt_b = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")
            
                status_a = a.get("status")
                status_b = b.get("status")

                has_amount_mismatch = amt_a is not None and amt_b is not None and amt_a != amt_b
                has_status_mismatch = status_a is not None and status_b is not None and status_a != status_b

                if has_amount_mismatch:
                    report["amount_mismatches"].append(key)
                if has_status_mismatch:
                    report["status_mismatches"].append(key)

                if not has_amount_mismatch and not has_status_mismatch:
                    report["matched"].append(key)
    return report
