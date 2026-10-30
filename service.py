
"""Order lifecycle, refund processing and reconciliation service."""

from copy import deepcopy


VALID_EVENTS = {
    "payment_confirmed",
    "restaurant_accepted",
    "restaurant_rejected",
    "cancel_requested",
    "dispatch_started",
    "order_delivered",
    "refund_processed",
}


def _is_valid_paise(value):
    """Accept positive integer paise, excluding bool."""
    return type(value) is int and value > 0


def apply_order_event(order: dict, event: dict) -> dict:
    """Apply one event and return an updated copy of the order."""

    if not isinstance(order, dict):
        return order

    out = deepcopy(order)

    if not isinstance(event, dict):
        return out

    # Ensure expected fields exist without mutating the input.
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)

    processed_ids = out.get("processed_event_ids")
    if not isinstance(processed_ids, list):
        processed_ids = []

    out["processed_event_ids"] = processed_ids

    event_id = event.get("event_id")
    event_type = event.get("type")

    # An event needs a usable ID and a recognized type.
    if not isinstance(event_id, str) or not event_id.strip():
        return out

    if not isinstance(event_type, str) or event_type not in VALID_EVENTS:
        return out
    

    # Prevent replaying an already processed event.
    if event_id in processed_ids:
        return out

    status = out.get("status")
    payment_status = out.get("payment_status")

    if event_type == "payment_confirmed":

        if payment_status == "UNPAID":
            out["payment_status"] = "PAID"

    elif event_type == "restaurant_accepted":

        if status == "PLACED":
            out["status"] = "ACCEPTED"

    elif event_type == "restaurant_rejected":

        if status == "PLACED":
            out["status"] = "REJECTED"

            total = out.get("total_paise")

            if payment_status == "PAID" and _is_valid_paise(total):
                out["refund_due_paise"] = total

    elif event_type == "cancel_requested":

        if status in ("PLACED", "ACCEPTED"):
            out["status"] = "CANCELLED"

            total = out.get("total_paise")

            if payment_status == "PAID" and _is_valid_paise(total):
                out["refund_due_paise"] = total

    elif event_type == "dispatch_started":

        if status == "ACCEPTED":
            out["status"] = "OUT_FOR_DELIVERY"

    elif event_type == "order_delivered":

        if status == "OUT_FOR_DELIVERY":
            out["status"] = "DELIVERED"

    elif event_type == "refund_processed":

        amount = event.get("amount_paise")
        due = out.get("refund_due_paise")
        refunded = out.get("refunded_paise")

        # Validate the complete refund context before changing state.
        if not (
            status in ("REJECTED", "CANCELLED")
            and payment_status == "PAID"
            and _is_valid_paise(due)
            and type(refunded) is int
            and refunded >= 0
            and _is_valid_paise(amount)
        ):
            return out

        outstanding = due - refunded

        if outstanding <= 0 or amount > outstanding:
            return out

        out["refunded_paise"] = refunded + amount

        if out["refunded_paise"] == due:
            out["payment_status"] = "REFUNDED"

    # Record recognized events once, including valid events that
    # do not cause a state transition.
    out["processed_event_ids"].append(event_id)

    return out



def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare internal and provider summaries using their respective schemas."""

    if not isinstance(internal, list):
        internal = []

    if not isinstance(provider, list):
        provider = []

    left = {
        row["order_id"]: row
        for row in internal
        if isinstance(row, dict)
        and isinstance(row.get("order_id"), str)
        and row["order_id"].strip()
    }

    right = {
        row["order_id"]: row
        for row in provider
        if isinstance(row, dict)
        and isinstance(row.get("order_id"), str)
        and row["order_id"].strip()
    }

    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    for order_id in sorted(set(left) | set(right)):

        if order_id not in right:
            report["missing_from_provider"].append(order_id)
            continue

        if order_id not in left:
            report["missing_from_internal"].append(order_id)
            continue

        internal_record = left[order_id]
        provider_record = right[order_id]

        # Internal model uses total_paise.
        # Provider summary uses amount_paise.
        internal_amount = internal_record.get(
            "total_paise",
            internal_record.get("amount_paise")
        )

        provider_amount = provider_record.get(
            "amount_paise",
            provider_record.get("total_paise")
        )

        amount_matches = (
            internal_amount is not None
            and provider_amount is not None
            and type(internal_amount) is int
            and type(provider_amount) is int
            and internal_amount == provider_amount
        )

        status_matches = (
            "status" in internal_record
            and "status" in provider_record
            and internal_record["status"] == provider_record["status"]
        )

        if not amount_matches:
            report["amount_mismatches"].append(order_id)

        if not status_matches:
            report["status_mismatches"].append(order_id)

        if amount_matches and status_matches:
            report["matched"].append(order_id)

    return report
