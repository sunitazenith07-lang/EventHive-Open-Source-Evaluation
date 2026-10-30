"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    if not isinstance(order, dict):
        return {}
    out = deepcopy(order)
    out.setdefault("status", "PLACED")
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    kind = event.get("type")

    if kind == "payment_confirmed":
        if out.get("payment_status") != "REFUNDED":
            out["payment_status"] = "PAID"
            if out.get("status") in ("REJECTED", "CANCELLED") and out.get("refund_due_paise", 0) == 0:
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
        # Eligibility: status must be REJECTED or CANCELLED, payment_status must be PAID, refund_due_paise > 0
        if (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
            and out.get("refund_due_paise", 0) > 0
        ):
            amount = event.get("amount_paise")
            if isinstance(amount, int) and not isinstance(amount, bool) and amount > 0:
                remaining_due = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)
                if amount <= remaining_due:
                    out["refunded_paise"] += amount
                    if out["refunded_paise"] == out["refund_due_paise"]:
                        out["payment_status"] = "REFUNDED"

    if event_id is not None:
        out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left = {r.get("order_id"): r for r in (internal or []) if isinstance(r, dict)}
    right = {r.get("order_id"): r for r in (provider or []) if isinstance(r, dict)}
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
            a_amt = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
            b_amt = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")
            a_status = a.get("status")
            b_status = b.get("status")

            amount_match = (a_amt == b_amt)
            status_match = (a_status == b_status)

            if not amount_match:
                report["amount_mismatches"].append(key)
            if not status_match:
                report["status_mismatches"].append(key)
            if amount_match and status_match:
                report["matched"].append(key)
    return report


def summarise_orders_by_state(orders: list[dict]) -> dict:
    """Summarise order count and total paise grouped by (status, payment_status).

    Optional stretch implementation.
    """
    summary = {}
    for o in orders or []:
        if not isinstance(o, dict):
            continue
        status = o.get("status", "UNKNOWN")
        payment_status = o.get("payment_status", "UNKNOWN")
        key = f"{status}:{payment_status}"
        amt = o.get("total_paise") if "total_paise" in o else o.get("amount_paise", 0)
        if key not in summary:
            summary[key] = {"count": 0, "total_paise": 0}
        summary[key]["count"] += 1
        summary[key]["total_paise"] += (amt or 0)
    return summary
