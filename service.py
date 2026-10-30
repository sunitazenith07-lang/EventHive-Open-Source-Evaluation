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
    out.setdefault("status", "PLACED")
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    event_id = event.get("event_id")
    kind = event.get("type")

    # Idempotency: replaying an already-processed event must not mutate state or duplicate ID
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    if kind == "payment_confirmed":
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
        # Eligibility: only PAID, cancelled or rejected orders with outstanding refund due
        status = out.get("status")
        payment_status = out.get("payment_status")
        due = out.get("refund_due_paise", 0)
        already_refunded = out.get("refunded_paise", 0)
        remaining_due = due - already_refunded

        amount = event.get("amount_paise")
        # Amount must be positive integer paise, not exceeding remaining due
        if (
            status in ("REJECTED", "CANCELLED")
            and payment_status == "PAID"
            and remaining_due > 0
            and type(amount) is int
            and amount > 0
            and amount <= remaining_due
        ):
            out["refunded_paise"] = already_refunded + amount
            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"

    if event_id is not None:
        out["processed_event_ids"].append(event_id)

    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    int_list = internal if isinstance(internal, list) else []
    prov_list = provider if isinstance(provider, list) else []

    left = {r["order_id"]: r for r in int_list if isinstance(r, dict) and r.get("order_id") is not None}
    right = {r["order_id"]: r for r in prov_list if isinstance(r, dict) and r.get("order_id") is not None}

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
            a_status = a.get("status")
            b_status = b.get("status")

            amount_mismatch = (a_amount != b_amount)
            status_mismatch = (a_status != b_status)

            if amount_mismatch:
                report["amount_mismatches"].append(key)
            if status_mismatch:
                report["status_mismatches"].append(key)
            if not amount_mismatch and not status_mismatch:
                report["matched"].append(key)

    return report
