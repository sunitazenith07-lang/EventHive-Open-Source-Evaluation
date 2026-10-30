"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    if not isinstance(order, dict):
        return {}
    if not isinstance(event, dict):
        return deepcopy(order)

    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    event_id = event.get("event_id")
    # Ignore duplicate events for idempotency
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    kind = event.get("type")

    if kind == "payment_confirmed":
        if out.get("payment_status") == "UNPAID":
            out["payment_status"] = "PAID"
            # If order was already cancelled or rejected, record refund due
            if out.get("status") in ("REJECTED", "CANCELLED"):
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
        amount = event.get("amount_paise")
        # Validate integer paise, positive amount, and order eligibility
        if type(amount) is int and amount > 0:
            if out.get("status") in ("REJECTED", "CANCELLED") and out.get("payment_status") == "PAID":
                remaining = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)
                if amount <= remaining:
                    out["refunded_paise"] += amount
                    if out["refunded_paise"] == out.get("refund_due_paise", 0):
                        out["payment_status"] = "REFUNDED"

    # Track processed event id for idempotency
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
    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            a_amount = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
            b_amount = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")
            has_mismatch = False
            if a_amount != b_amount:
                report["amount_mismatches"].append(key)
                has_mismatch = True
            # Check for mismatched order status
            if a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)
                has_mismatch = True
            if not has_mismatch:
                report["matched"].append(key)
    return report
