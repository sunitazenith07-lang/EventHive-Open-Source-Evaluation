
"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order."""
    out = deepcopy(order)

    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")

    # Idempotency: ignore an event that was already processed.
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    if kind == "payment_confirmed":
        out["payment_status"] = "PAID"

    elif kind == "restaurant_accepted":
        if out.get("status") == "PLACED":
            out["status"] = "ACCEPTED"

    elif kind == "restaurant_rejected":
        if out.get("status") == "PLACED":
            out["status"] = "REJECTED"
            if out["payment_status"] == "PAID":
                out["refund_due_paise"] = out.get("total_paise", 0)

    elif kind == "cancel_requested":
        if out.get("status") in ("PLACED", "ACCEPTED"):
            out["status"] = "CANCELLED"
            if out["payment_status"] == "PAID":
                out["refund_due_paise"] = out.get("total_paise", 0)

    elif kind == "dispatch_started":
        if out.get("status") == "ACCEPTED":
            out["status"] = "OUT_FOR_DELIVERY"

    elif kind == "order_delivered":
        if out.get("status") == "OUT_FOR_DELIVERY":
            out["status"] = "DELIVERED"

    elif kind == "refund_processed":
        amount = event.get("amount_paise")

        valid_amount = (
            isinstance(amount, int)
            and not isinstance(amount, bool)
            and amount > 0
        )

        eligible = (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
            and out.get("refund_due_paise", 0) > 0
        )

        outstanding = (
            out.get("refund_due_paise", 0)
            - out.get("refunded_paise", 0)
        )

        if valid_amount and eligible and amount <= outstanding:
            out["refunded_paise"] += amount

            if out["refunded_paise"] == out["refund_due_paise"]:
                out["payment_status"] = "REFUNDED"

    else:
        # Unknown event: safely ignore it.
        return out

    if event_id is not None:
        out["processed_event_ids"].append(event_id)

    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left = {
        r.get("order_id"): r
        for r in internal
        if isinstance(r, dict) and r.get("order_id") is not None
    }
    right = {
        r.get("order_id"): r
        for r in provider
        if isinstance(r, dict) and r.get("order_id") is not None
    }

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
            continue

        if key not in left:
            report["missing_from_internal"].append(key)
            continue

        a = left[key]
        b = right[key]

        amount_mismatch = (
            a.get("amount_paise") != b.get("amount_paise")
        )
        status_mismatch = (
            a.get("status") != b.get("status")
        )

        if amount_mismatch:
            report["amount_mismatches"].append(key)

        if status_mismatch:
            report["status_mismatches"].append(key)

        if not amount_mismatch and not status_mismatch:
            report["matched"].append(key)

    return report
