"""Order lifecycle, refund service, and reconciliation engine."""
from copy import deepcopy


def _get_order_amount(order: dict) -> int:
    """Helper to extract order total across total_paise and amount_paise schema conventions."""
    if "total_paise" in order and order["total_paise"] is not None:
        return order["total_paise"]
    if "amount_paise" in order and order["amount_paise"] is not None:
        return order["amount_paise"]
    return 0


def apply_order_event(order: dict, event: dict) -> dict:
    """Applies an event idempotently to an order dictionary without mutating the input."""
    if not isinstance(order, dict):
        return {}

    out = deepcopy(order)
    out["status"] = out.get("status") or "PLACED"
    out["payment_status"] = out.get("payment_status") or "UNPAID"
    out["refund_due_paise"] = out.get("refund_due_paise") if out.get("refund_due_paise") is not None else 0
    out["refunded_paise"] = out.get("refunded_paise") if out.get("refunded_paise") is not None else 0

    if not isinstance(out.get("processed_event_ids"), list):
        out["processed_event_ids"] = []

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
                out["refund_due_paise"] = _get_order_amount(out)

    elif kind == "restaurant_accepted" and out.get("status") == "PLACED":
        out["status"] = "ACCEPTED"

    elif kind == "restaurant_rejected" and out.get("status") == "PLACED":
        out["status"] = "REJECTED"
        if out.get("payment_status") == "PAID":
            out["refund_due_paise"] = _get_order_amount(out)

    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out.get("payment_status") == "PAID":
            out["refund_due_paise"] = _get_order_amount(out)

    elif kind == "dispatch_started" and out.get("status") == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"

    elif kind == "order_delivered" and out.get("status") == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"

    elif kind == "refund_processed":
        if (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
            and out.get("refund_due_paise", 0) > 0
        ):
            amount = event.get("amount_paise")
            if type(amount) is int and amount > 0:
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
    left = {r.get("order_id"): r for r in (internal or []) if isinstance(r, dict) and r.get("order_id") is not None}
    right = {r.get("order_id"): r for r in (provider or []) if isinstance(r, dict) and r.get("order_id") is not None}

    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    all_keys = sorted(set(left) | set(right), key=lambda x: str(x))

    for key in all_keys:
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            a_amt = _get_order_amount(a)
            b_amt = _get_order_amount(b)
            a_status = a.get("status")
            b_status = b.get("status")

            has_amount_diff = (a_amt != b_amt)
            has_status_diff = (a_status != b_status)

            if has_amount_diff:
                report["amount_mismatches"].append(key)
            if has_status_diff:
                report["status_mismatches"].append(key)
            if not has_amount_diff and not has_status_diff:
                report["matched"].append(key)

    return report


def summarise_orders_by_state(orders: list[dict]) -> dict:
    """Summarise order counts grouped by status state."""
    summary = {}
    for o in orders or []:
        if not isinstance(o, dict):
            continue
        status = o.get("status") or "UNKNOWN"
        summary[status] = summary.get(status, 0) + 1
    return summary