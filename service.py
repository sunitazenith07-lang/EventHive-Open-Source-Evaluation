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

    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    handled = False

    if kind == "payment_confirmed":
        out["payment_status"] = "PAID"
        handled = True
    elif kind == "restaurant_accepted" and out.get("status") == "PLACED":
        out["status"] = "ACCEPTED"
        handled = True
    elif kind == "restaurant_rejected" and out.get("status") == "PLACED":
        out["status"] = "REJECTED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)
        handled = True
    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)
        handled = True
    elif kind == "dispatch_started" and out.get("status") == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"
        handled = True
    elif kind == "order_delivered" and out.get("status") == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"
        handled = True
    elif kind == "refund_processed":
        handled = True
        eligible = (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
            and out.get("refund_due_paise", 0) > 0
        )
        if eligible:
            amount = event.get("amount_paise")
            remaining = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)
            if (
                isinstance(amount, int)
                and not isinstance(amount, bool)
                and 0 < amount <= remaining
            ):
                out["refunded_paise"] += amount
                if out["refunded_paise"] >= out.get("refund_due_paise", 0):
                    out["payment_status"] = "REFUNDED"

    if not handled:
        return out

    if event_id is not None:
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

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)
            elif a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)
            else:
                report["matched"].append(key)

    return report
