"""Order lifecycle, refund handling, and provider reconciliation."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Apply an event to a copy of the order, without replaying event IDs."""
    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")

    if event_id in out["processed_event_ids"]:
        return out

    if kind == "payment_confirmed":
        if out.get("payment_status") == "UNPAID":
            out["payment_status"] = "PAID"
    elif kind == "restaurant_accepted" and out.get("status") == "PLACED":
        out["status"] = "ACCEPTED"
    elif kind == "restaurant_rejected" and out.get("status") == "PLACED":
        out["status"] = "REJECTED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)
    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)
    elif kind == "dispatch_started" and out.get("status") == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"
    elif kind == "order_delivered" and out.get("status") == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"
    elif kind == "refund_processed":
        amount = event.get("amount_paise")
        due = out["refund_due_paise"]
        refunded = out["refunded_paise"]
        eligible = (
            out.get("status") in ("CANCELLED", "REJECTED")
            and out["payment_status"] == "PAID"
            and type(amount) is int
            and amount > 0
            and type(due) is int
            and type(refunded) is int
            and due > 0
            and 0 <= refunded < due
            and amount <= due - refunded
        )
        if eligible:
            out["refunded_paise"] += amount
            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"

    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order ID, deterministically."""
    left = {r.get("order_id"): r for r in internal}
    right = {r.get("order_id"): r for r in provider}
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }
    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
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
            if (
                a.get("amount_paise") == b.get("amount_paise")
                and a.get("status") == b.get("status")
            ):
                report["matched"].append(key)
    return report
