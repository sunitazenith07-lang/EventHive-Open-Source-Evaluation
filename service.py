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
        amount = event.get("amount_paise")
        if (
            type(amount) is int
            and amount > 0
            and out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
        ):
            due = out.get("refund_due_paise", 0)
            current = out.get("refunded_paise", 0)
            if due > 0 and (current + amount <= due):
                out["refunded_paise"] = current + amount
                if out["refunded_paise"] == due:
                    out["payment_status"] = "REFUNDED"

    if event_id is not None:
        out["processed_event_ids"].append(event_id)

    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    left = {}
    for r in internal or []:
        if isinstance(r, dict) and r.get("order_id") is not None:
            left[r["order_id"]] = r

    right = {}
    for r in provider or []:
        if isinstance(r, dict) and r.get("order_id") is not None:
            right[r["order_id"]] = r

    def _get_amount(rec: dict):
        if "amount_paise" in rec and rec["amount_paise"] is not None:
            return rec["amount_paise"]
        return rec.get("total_paise")

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amount_diff = _get_amount(a) != _get_amount(b)
            status_diff = a.get("status") != b.get("status")

            if amount_diff:
                report["amount_mismatches"].append(key)
            if status_diff:
                report["status_mismatches"].append(key)
            if not amount_diff and not status_diff:
                report["matched"].append(key)

    return report
