"""Order lifecycle, refund processing, and reconciliation logic."""

from copy import deepcopy


EVENT_TYPES = frozenset(
    {
        "payment_confirmed",
        "restaurant_accepted",
        "restaurant_rejected",
        "cancel_requested",
        "dispatch_started",
        "order_delivered",
        "refund_processed",
    }
)


def _apply_refund(order: dict, amount: object) -> None:
    """Apply a valid refund to an eligible order."""
    due = order.get("refund_due_paise")
    refunded = order.get("refunded_paise")

    eligible = (
        order.get("status") in ("CANCELLED", "REJECTED")
        and order.get("payment_status") == "PAID"
        and isinstance(due, int)
        and not isinstance(due, bool)
        and due > 0
        and isinstance(refunded, int)
        and not isinstance(refunded, bool)
        and 0 <= refunded < due
    )
    valid_amount = (
        isinstance(amount, int)
        and not isinstance(amount, bool)
        and amount > 0
    )

    if not eligible or not valid_amount or amount > due - refunded:
        return

    order["refunded_paise"] = refunded + amount
    if order["refunded_paise"] == due:
        order["payment_status"] = "REFUNDED"


def apply_order_event(order: dict, event: dict) -> dict:
    """Return a copy of the order updated by one supported event."""
    updated = deepcopy(order)
    updated.setdefault("payment_status", "UNPAID")
    updated.setdefault("refund_due_paise", 0)
    updated.setdefault("refunded_paise", 0)
    updated.setdefault("processed_event_ids", [])

    if not isinstance(updated["processed_event_ids"], list):
        return updated
    if not isinstance(event, dict):
        return updated

    event_id = event.get("event_id")
    event_type = event.get("type")
    if (
        not isinstance(event_id, str)
        or not event_id
        or not isinstance(event_type, str)
        or event_type not in EVENT_TYPES
    ):
        return updated

    if event_id in updated["processed_event_ids"]:
        return updated

    status = updated.get("status")
    if event_type == "payment_confirmed":
        updated["payment_status"] = "PAID"
    elif event_type == "restaurant_accepted" and status == "PLACED":
        updated["status"] = "ACCEPTED"
    elif event_type == "restaurant_rejected" and status == "PLACED":
        updated["status"] = "REJECTED"
        if updated["payment_status"] == "PAID":
            updated["refund_due_paise"] = updated.get("total_paise", 0)
    elif event_type == "cancel_requested" and status in ("PLACED", "ACCEPTED"):
        updated["status"] = "CANCELLED"
        if updated["payment_status"] == "PAID":
            updated["refund_due_paise"] = updated.get("total_paise", 0)
    elif event_type == "dispatch_started" and status == "ACCEPTED":
        updated["status"] = "OUT_FOR_DELIVERY"
    elif event_type == "order_delivered" and status == "OUT_FOR_DELIVERY":
        updated["status"] = "DELIVERED"
    elif event_type == "refund_processed":
        _apply_refund(updated, event.get("amount_paise"))

    updated["processed_event_ids"].append(event_id)
    return updated


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare internal and provider order summaries by order ID."""
    internal_by_id = {
        record["order_id"]: record
        for record in internal
        if isinstance(record, dict)
        and isinstance(record.get("order_id"), str)
        and record["order_id"]
    }
    provider_by_id = {
        record["order_id"]: record
        for record in provider
        if isinstance(record, dict)
        and isinstance(record.get("order_id"), str)
        and record["order_id"]
    }

    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }
    order_ids = sorted(
        set(internal_by_id) | set(provider_by_id),
        key=lambda order_id: str(order_id),
    )

    for order_id in order_ids:
        if order_id not in provider_by_id:
            report["missing_from_provider"].append(order_id)
            continue
        if order_id not in internal_by_id:
            report["missing_from_internal"].append(order_id)
            continue

        internal_record = internal_by_id[order_id]
        provider_record = provider_by_id[order_id]
        amount_matches = (
            internal_record.get("amount_paise")
            == provider_record.get("amount_paise")
        )
        status_matches = internal_record.get("status") == provider_record.get("status")

        if not amount_matches:
            report["amount_mismatches"].append(order_id)
        if not status_matches:
            report["status_mismatches"].append(order_id)
        if amount_matches and status_matches:
            report["matched"].append(order_id)

    return report
