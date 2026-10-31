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
    # Read the event identity and type before changing the order.
    event_id=event.get("event_id")
    if event_id == "":
        return out
    kind=event.get("type")
    valid_event_types = {
        "payment_confirmed",
        "restaurant_accepted",
        "restaurant_rejected",
        "cancel_requested",
        "dispatch_started",
        "order_delivered",
        "refund_processed",
    }

    # Ignore unsupported event types so unknown events cannot change state.
    if kind not in valid_event_types:
        return out

    # A supplied event ID must be a non-empty string.
    if event_id is not None and (
        not isinstance(event_id, str) or not event_id.strip()
    ):
        return out

    # Process each identified event only once.
    if event_id in out["processed_event_ids"]:
        return out

    # Apply only valid transitions from the order's current state.
    if kind == "payment_confirmed" and out.get("payment_status") == "UNPAID":
        out["payment_status"] = "PAID"
    elif kind=="restaurant_accepted" and out.get("status")=="PLACED":
        out["status"]="ACCEPTED"
    elif kind=="restaurant_rejected" and out.get("status")=="PLACED":
        out["status"]="REJECTED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="cancel_requested" and out.get("status") in ("PLACED","ACCEPTED"):
        out["status"]="CANCELLED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="dispatch_started" and out.get("status")=="ACCEPTED":
        out["status"]="OUT_FOR_DELIVERY"
    elif kind=="order_delivered" and out.get("status")=="OUT_FOR_DELIVERY":
        out["status"]="DELIVERED"
    # Refunds need an ID so they can be tracked and protected from duplicates.
    elif kind == "refund_processed" and event_id is not None:
        amount = event.get("amount_paise")
        refund_due = out.get("refund_due_paise", 0)
        already_refunded = out.get("refunded_paise", 0)

        # Refund only rejected/cancelled, paid orders with money still due.
        eligible = (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
            and out.get("refund_due_paise", 0) > out.get("refunded_paise", 0)
        )

        # Accept only a positive integer amount within the remaining refund.
        valid_amount = (
            type(amount) is int
            and amount > 0
            and type(refund_due) is int
            and type(already_refunded) is int
            and 0 < refund_due - already_refunded
            and amount <= refund_due - already_refunded
        )

        if eligible and valid_amount:
            out["refunded_paise"] = already_refunded + amount

            # Mark payment refunded only when the full due amount is returned.
            if out["refunded_paise"] == refund_due:
                out["payment_status"] = "REFUNDED"

    # Record identified events so later duplicates can be ignored.
    if event_id is not None:
        out["processed_event_ids"].append(event_id)

    return out



def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare internal and provider transaction summaries by order_id."""
    # Validate IDs before building lookup maps; each order must be unambiguous.
    internal_ids = [r.get("order_id") for r in internal]
    provider_ids = [r.get("order_id") for r in provider]

    if len(internal_ids) != len(set(internal_ids)):
        raise ValueError("Duplicate order_id in internal records")

    if len(provider_ids) != len(set(provider_ids)):
        raise ValueError("Duplicate order_id in provider records")
    if any(not r.get("order_id") for r in internal):
        raise ValueError("Missing order_id in internal records")
    if any(not r.get("order_id") for r in provider):
        raise ValueError("Missing order_id in provider records")
    # Index both sources by order ID so corresponding records can be compared.
    left = {r.get("order_id"): r for r in internal}
    right = {r.get("order_id"): r for r in provider}

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

            # Use primary amount fields, falling back when a value is None.
            internal_amount = a.get("total_paise")
            if internal_amount is None:
                internal_amount = a.get("amount_paise")

            provider_amount = b.get("amount_paise")
            if provider_amount is None:
                provider_amount = b.get("total_paise")

            # Check amount and status separately so both problems are reported.
            amount_mismatch = internal_amount != provider_amount
            status_mismatch = a.get("status") != b.get("status")

            if amount_mismatch:
                report["amount_mismatches"].append(key)

            if status_mismatch:
                report["status_mismatches"].append(key)

            # Match only when both amount and status agree.
            if not amount_mismatch and not status_mismatch:
                report["matched"].append(key)

    return report
