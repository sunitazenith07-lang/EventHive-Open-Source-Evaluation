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

    # 1. Idempotency: If this event was already processed, ignore replay
    if event_id is not None and event_id in out["processed_event_ids"]:
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
        # 2. Refund validation:
        # Must be an eligible order (CANCELLED or REJECTED, PAID, and refund due > 0)
        is_eligible = (
            out.get("status") in ("CANCELLED", "REJECTED")
            and out.get("payment_status") == "PAID"
            and out.get("refund_due_paise", 0) > 0
        )
        amount = event.get("amount_paise")
        # Amount must be a strict positive integer (reject bool, float, str, negative, zero)
        is_valid_amount = isinstance(amount, int) and not isinstance(amount, bool) and amount > 0

        if is_eligible and is_valid_amount:
            remaining_due = out["refund_due_paise"] - out["refunded_paise"]
            if amount <= remaining_due:
                out["refunded_paise"] += amount
                if out["refunded_paise"] >= out["refund_due_paise"]:
                    out["payment_status"] = "REFUNDED"

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
        "status_mismatches": []
    }
    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            # Handle either total_paise or amount_paise key
            a_amt = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
            b_amt = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")
            a_status = a.get("status")
            b_status = b.get("status")

            has_amount_mismatch = (a_amt != b_amt)
            has_status_mismatch = (a_status != b_status)

            if has_amount_mismatch:
                report["amount_mismatches"].append(key)
            if has_status_mismatch:
                report["status_mismatches"].append(key)
            if not has_amount_mismatch and not has_status_mismatch:
                report["matched"].append(key)

    return report
