"""Order lifecycle, refund processing, and reconciliation for synthetic records."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return a new order after a valid, not-yet-processed event."""
    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])
    if not isinstance(event, dict):
        return out
    event_id = event.get("event_id")
    kind = event.get("type")
    if not isinstance(event_id, str) or not event_id.strip() or event_id in out["processed_event_ids"]:
        return out
    if kind not in {"payment_confirmed", "restaurant_accepted", "restaurant_rejected", "cancel_requested", "dispatch_started", "order_delivered", "refund_processed"}:
        return out
    status = out.get("status")
    if kind == "payment_confirmed" and status in {"PLACED", "ACCEPTED"} and out["payment_status"] == "UNPAID":
        out["payment_status"] = "PAID"
    elif kind == "restaurant_accepted" and status == "PLACED":
        out["status"] = "ACCEPTED"
    elif kind == "restaurant_rejected" and status == "PLACED":
        out["status"] = "REJECTED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = max(0, out.get("total_paise", 0))
    elif kind == "cancel_requested" and status in {"PLACED", "ACCEPTED"}:
        out["status"] = "CANCELLED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = max(0, out.get("total_paise", 0))
    elif kind == "dispatch_started" and status == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"
    elif kind == "order_delivered" and status == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"
    elif kind == "refund_processed" and status in {"CANCELLED", "REJECTED"} and out["payment_status"] == "PAID":
        amount = event.get("amount_paise")
        due = out.get("refund_due_paise", 0)
        refunded = out.get("refunded_paise", 0)
        if type(amount) is int and amount > 0 and type(due) is int and type(refunded) is int and refunded + amount <= due:
            out["refunded_paise"] = refunded + amount
            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"
    else:
        return out
    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare summaries by order ID and return sorted, separate discrepancies."""
    left = {r.get("order_id"): r for r in internal if isinstance(r, dict) and r.get("order_id") is not None}
    right = {r.get("order_id"): r for r in provider if isinstance(r, dict) and r.get("order_id") is not None}
    report = {"matched": [], "missing_from_provider": [], "missing_from_internal": [], "amount_mismatches": [], "status_mismatches": []}
    for key in sorted(set(left) | set(right), key=lambda value: str(value)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)
            if a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)
            if a.get("amount_paise") == b.get("amount_paise") and a.get("status") == b.get("status"):
                report["matched"].append(key)
    return report
