"""Order lifecycle and refund service."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])
    event_id = event.get("event_id")
    kind = event.get("type")

    if event_id and event_id in out["processed_event_ids"]:
        return out

    if kind == "payment_confirmed":
        out["payment_status"] = "PAID"
        if out.get("status") in ("REJECTED", "CANCELLED"):
            out["refund_due_paise"] = out.get("total_paise", 0)
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
        is_eligible = (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
            and out.get("refund_due_paise", 0) > 0
        )
        amt = event.get("amount_paise")
        is_valid_amount = (
            type(amt) is int
            and amt > 0
            and (out["refunded_paise"] + amt <= out.get("refund_due_paise", 0))
        )
        if is_eligible and is_valid_amount:
            out["refunded_paise"] += amt
            if out["refunded_paise"] == out.get("refund_due_paise", 0):
                out["payment_status"] = "REFUNDED"

    if event_id:
        out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left = {r.get("order_id"): r for r in internal}
    right = {r.get("order_id"): r for r in provider}
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    def _get_amount(record: dict):
        if "amount_paise" in record:
            return record.get("amount_paise")
        return record.get("total_paise")

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amt_a = _get_amount(a)
            amt_b = _get_amount(b)
            if amt_a != amt_b:
                report["amount_mismatches"].append(key)
            elif a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)
            else:
                report["matched"].append(key)
    return report
