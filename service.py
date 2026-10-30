"""Order lifecycle and refund reconciliation service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    if not isinstance(order, dict):
        return {}

    out = deepcopy(order)
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
        if out.get("payment_status") == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)
    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out.get("payment_status") == "PAID":
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
        amount = event.get("amount_paise")
        if is_eligible and type(amount) is int and amount > 0:
            outstanding = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)
            if amount <= outstanding:
                out["refunded_paise"] += amount
                if out["refunded_paise"] >= out.get("refund_due_paise", 0):
                    out["payment_status"] = "REFUNDED"

    if event_id is not None:
        out["processed_event_ids"].append(event_id)

    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left = {
        r.get("order_id"): r
        for r in (internal or [])
        if isinstance(r, dict) and r.get("order_id") is not None
    }
    right = {
        r.get("order_id"): r
        for r in (provider or [])
        if isinstance(r, dict) and r.get("order_id") is not None
    }
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    def _extract_amount(record: dict):
        if "amount_paise" in record and record["amount_paise"] is not None:
            return record["amount_paise"]
        if "total_paise" in record and record["total_paise"] is not None:
            return record["total_paise"]
        return None

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amount_a = _extract_amount(a)
            amount_b = _extract_amount(b)
            status_a = a.get("status")
            status_b = b.get("status")

            has_amount_diff = amount_a != amount_b
            has_status_diff = status_a != status_b

            if has_amount_diff:
                report["amount_mismatches"].append(key)
            if has_status_diff:
                report["status_mismatches"].append(key)
            if not has_amount_diff and not has_status_diff:
                report["matched"].append(key)

    return report


def summarise_orders_by_state(orders: list[dict]) -> dict[str, int]:
    """Summarise count of orders grouped by their lifecycle status."""
    summary: dict[str, int] = {}
    for r in (orders or []):
        if isinstance(r, dict):
            status = str(r.get("status", "UNKNOWN"))
            summary[status] = summary.get(status, 0) + 1
    return dict(sorted(summary.items()))

