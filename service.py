"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    if not isinstance(order, dict):
        return {}

    out=deepcopy(order)
    out.setdefault("payment_status","UNPAID")
    out.setdefault("refund_due_paise",0)
    out.setdefault("refunded_paise",0)
    out.setdefault("processed_event_ids",[])

    if not isinstance(event, dict):
        return out

    event_id=event.get("event_id")
    kind=event.get("type")

    if event_id in out.get("processed_event_ids", []):
        return out

    if kind not in {
        "payment_confirmed",
        "restaurant_accepted",
        "restaurant_rejected",
        "cancel_requested",
        "dispatch_started",
        "order_delivered",
        "refund_processed",
    }:
        return out

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
    elif kind=="refund_processed":
        amount=event.get("amount_paise")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return out
        if out.get("payment_status") != "PAID":
            return out
        if out.get("status") not in ("CANCELLED","REJECTED"):
            return out
        outstanding=max(out.get("refund_due_paise",0)-out.get("refunded_paise",0),0)
        if amount > outstanding or outstanding <= 0:
            return out
        out["refunded_paise"] += amount
        if out["refunded_paise"] >= out.get("refund_due_paise",0):
            out["payment_status"]="REFUNDED"

    if event_id is not None:
        out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left={}
    for row in internal or []:
        if not isinstance(row, dict):
            continue
        key=row.get("order_id")
        if key is None:
            continue
        left[key]=row

    right={}
    for row in provider or []:
        if not isinstance(row, dict):
            continue
        key=row.get("order_id")
        if key is None:
            continue
        right[key]=row

    report={"matched":[],"missing_from_provider":[],"missing_from_internal":[],
            "amount_mismatches":[],"status_mismatches":[]}
    for key in sorted(set(left)|set(right),key=lambda x:str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a,b=left[key],right[key]
            amount_mismatch = a.get("amount_paise") != b.get("amount_paise")
            status_mismatch = a.get("status") != b.get("status")
            if amount_mismatch:
                report["amount_mismatches"].append(key)
            if status_mismatch:
                report["status_mismatches"].append(key)
            if not amount_mismatch and not status_mismatch:
                report["matched"].append(key)
    return report


if __name__ == "__main__":
    from fixtures import sample_orders, sample_provider_orders

    report = reconcile_orders(sample_orders(), sample_provider_orders())
    print("Order reconciliation report")
    for key, value in report.items():
        print(f"{key}: {value}")
