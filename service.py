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

    # Idempotency check: if event_id has already been processed, return order unchanged immediately
    if event_id and event_id in out["processed_event_ids"]:
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
        # Validate amount is a strict integer (excluding booleans like True/False)
        if type(amount) is int and not isinstance(amount, bool):
            # Eligibility: status must be CANCELLED or REJECTED, payment_status must be PAID, and refund_due_paise > 0
            if (
                out.get("status") in ("CANCELLED", "REJECTED")
                and out.get("payment_status") == "PAID"
                and out.get("refund_due_paise", 0) > 0
            ):
                if amount > 0:
                    current_refunded = out.get("refunded_paise", 0)
                    refund_due = out.get("refund_due_paise", 0)
                    # Ensure refund does not exceed due amount
                    if current_refunded + amount <= refund_due:
                        out["refunded_paise"] = current_refunded + amount
                        # Set status to REFUNDED only when the full due amount has been processed
                        if out["refunded_paise"] == refund_due:
                            out["payment_status"] = "REFUNDED"

    if event_id and event_id not in out["processed_event_ids"]:
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
            has_mismatch = False

            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)
                has_mismatch = True

            if a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)
                has_mismatch = True

            if not has_mismatch:
                report["matched"].append(key)

    return report
