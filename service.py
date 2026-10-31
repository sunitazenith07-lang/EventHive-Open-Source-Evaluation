"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out=deepcopy(order)
    out.setdefault("payment_status","UNPAID")
    out.setdefault("refund_due_paise",0)
    out.setdefault("refunded_paise",0)
    out.setdefault("processed_event_ids",[])
    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")

    # Idempotency guard: duplicate events must not alter order state or processed_event_ids
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    # Order Lifecycle Transitions
    if kind == "payment_confirmed":
        out["payment_status"] = "PAID"
        if out.get("status") in ("CANCELLED", "REJECTED"):
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
        # Check order refund eligibility: order must be cancelled or rejected,
        # payment must be PAID, and refund_due_paise must be positive.
        if (out.get("status") in ("CANCELLED", "REJECTED")
                and out.get("payment_status") == "PAID"
                and out.get("refund_due_paise", 0) > 0):
            amount = event.get("amount_paise")
            # Amount must be a strict positive integer (exclude bools, floats, strings, None)
            if isinstance(amount, int) and not isinstance(amount, bool) and amount > 0:
                remaining = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)
                if amount <= remaining:
                    out["refunded_paise"] += amount
                    if out["refunded_paise"] >= out["refund_due_paise"]:
                        out["payment_status"] = "REFUNDED"

    if event_id is not None:
        out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left = {r.get("order_id"): r for r in internal if isinstance(r, dict) and r.get("order_id") is not None}
    right = {r.get("order_id"): r for r in provider if isinstance(r, dict) and r.get("order_id") is not None}
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
            amount_diff = _get_amount(a) != _get_amount(b)
            status_diff = a.get("status") != b.get("status")

            if amount_diff:
                report["amount_mismatches"].append(key)
            if status_diff:
                report["status_mismatches"].append(key)
            if not amount_diff and not status_diff:
                report["matched"].append(key)

    return report