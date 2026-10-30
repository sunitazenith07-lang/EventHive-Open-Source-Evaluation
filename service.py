"""Starter order lifecycle and refund service; all data is synthetic."""
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
    event_types = {
        "payment_confirmed",
        "restaurant_accepted",
        "restaurant_rejected",
        "cancel_requested",
        "dispatch_started",
        "order_delivered",
        "refund_processed",
    }
    if (
        not isinstance(event_id, str)
        or not event_id
        or not isinstance(kind, str)
        or kind not in event_types
    ):
        return out
    if event_id in out["processed_event_ids"]:
        return out

    if kind == "payment_confirmed":
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
        due = out.get("refund_due_paise")
        refunded = out.get("refunded_paise")
        eligible = (
            out.get("status") in ("CANCELLED", "REJECTED")
            and out["payment_status"] == "PAID"
            and isinstance(due, int)
            and not isinstance(due, bool)
            and due > 0
            and isinstance(refunded, int)
            and not isinstance(refunded, bool)
            and 0 <= refunded < due
        )
        valid_amount = (
            isinstance(amount, int)
            and not isinstance(amount, bool)
            and amount > 0
        )
        if eligible and valid_amount and amount <= due - refunded:
            out["refunded_paise"] += amount
            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"

    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left = {r["order_id"]: r for r in internal if r.get("order_id") is not None}
    right = {r["order_id"]: r for r in provider if r.get("order_id") is not None}
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
            a,b=left[key],right[key]
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
