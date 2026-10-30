"""Order lifecycle, refund processing, and reconciliation for synthetic records."""
from copy import deepcopy
from collections.abc import Iterable, Mapping


_EVENT_TYPES = {
    "payment_confirmed",
    "restaurant_accepted",
    "restaurant_rejected",
    "cancel_requested",
    "dispatch_started",
    "order_delivered",
    "refund_processed",
}


def _is_integer(value: object) -> bool:
    """Return True for integer paise values (excluding bool, an int subclass)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_event_id(event_id: object) -> bool:
    """Event IDs must be stable, non-empty scalar keys."""
    if isinstance(event_id, bool) or event_id is None:
        return False
    if isinstance(event_id, str):
        return bool(event_id.strip())
    return isinstance(event_id, int)


def apply_order_event(order: dict, event: dict) -> dict:
    """Return a deep-copied order after applying one recognized event.

    Events without a usable ID and unknown event types are ignored. A recognized
    event ID is recorded once, including a recognized event that is invalid for
    the current state; replaying that ID (even with a different payload) is a
    no-op. Refund values are integer paise only.
    """
    if not isinstance(order, Mapping):
        return deepcopy(order)

    out = deepcopy(dict(order))
    # Normalize these bookkeeping fields so malformed optional values cannot
    # cause a TypeError or mutate the caller's object.
    out.setdefault("payment_status", "UNPAID")
    if not isinstance(out.get("payment_status"), str):
        out["payment_status"] = "UNPAID"

    for field in ("refund_due_paise", "refunded_paise"):
        if not _is_integer(out.get(field)) or out.get(field, 0) < 0:
            out[field] = 0
        else:
            out.setdefault(field, 0)

    processed = out.get("processed_event_ids")
    if not isinstance(processed, list):
        processed = []
        out["processed_event_ids"] = processed

    if not isinstance(event, Mapping):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")
    if not _valid_event_id(event_id) or not isinstance(kind, str) or kind not in _EVENT_TYPES:
        return out
    # When an event carries an order ID, do not apply it to a different order.
    if "order_id" in event and (
        not _valid_order_id(event.get("order_id"))
        or event.get("order_id") != out.get("order_id")
    ):
        return out

    # Idempotency is checked before any side effect. Equality-based list lookup
    # also avoids requiring the stored ledger to be a set.
    if event_id in processed:
        return out

    status = out.get("status")
    payment_status = out.get("payment_status")

    if kind == "payment_confirmed":
        # Do not reverse a completed refund. A late confirmation against a
        # cancelled/rejected order creates a refund obligation for the payment.
        if payment_status != "REFUNDED":
            out["payment_status"] = "PAID"
            if status in ("REJECTED", "CANCELLED"):
                total = out.get("total_paise")
                if _is_integer(total) and total > 0:
                    out["refund_due_paise"] = max(out["refund_due_paise"], total)

    elif kind == "restaurant_accepted":
        if status == "PLACED":
            out["status"] = "ACCEPTED"

    elif kind == "restaurant_rejected":
        if status == "PLACED":
            out["status"] = "REJECTED"
            if payment_status == "PAID":
                total = out.get("total_paise")
                if _is_integer(total) and total >= 0:
                    out["refund_due_paise"] = total

    elif kind == "cancel_requested":
        if status in ("PLACED", "ACCEPTED"):
            out["status"] = "CANCELLED"
            if payment_status == "PAID":
                total = out.get("total_paise")
                if _is_integer(total) and total >= 0:
                    out["refund_due_paise"] = total

    elif kind == "dispatch_started":
        if status == "ACCEPTED":
            out["status"] = "OUT_FOR_DELIVERY"

    elif kind == "order_delivered":
        if status == "OUT_FOR_DELIVERY":
            out["status"] = "DELIVERED"

    elif kind == "refund_processed":
        amount = event.get("amount_paise")
        due = out["refund_due_paise"]
        refunded = out["refunded_paise"]
        outstanding = due - refunded
        eligible = status in ("REJECTED", "CANCELLED") and payment_status == "PAID"
        if (
            eligible
            and _is_integer(amount)
            and amount > 0
            and outstanding > 0
            and amount <= outstanding
        ):
            out["refunded_paise"] = refunded + amount
            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"

    # A recognized event ID is consumed once, whether it changed the state or
    # was rejected by the transition/validation rules.
    processed.append(event_id)
    return out


def _valid_order_id(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, int)


def _index_records(records: object) -> dict:
    """Index valid records by ID; later duplicate rows replace earlier rows."""
    indexed = {}
    if not isinstance(records, Iterable) or isinstance(records, (str, bytes, Mapping)):
        return indexed
    for record in records:
        if not isinstance(record, Mapping):
            continue
        order_id = record.get("order_id")
        if _valid_order_id(order_id):
            indexed[order_id] = record
    return indexed


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare summaries by order ID, returning sorted discrepancy buckets.

    Orders lacking a usable ID and non-mapping rows are ignored. For shared
    IDs, a missing amount or status is treated as a discrepancy rather than a
    successful match. An order can appear in both mismatch buckets.
    """
    left = _index_records(internal)
    right = _index_records(provider)
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    keys = set(left) | set(right)
    for key in sorted(keys, key=lambda value: (type(value).__name__, str(value))):
        if key not in right:
            report["missing_from_provider"].append(key)
            continue
        if key not in left:
            report["missing_from_internal"].append(key)
            continue

        internal_row = left[key]
        provider_row = right[key]
        # Internal order objects use total_paise; reconciliation-only test
        # rows may already use amount_paise. Provider summaries use amount_paise.
        internal_amount = internal_row.get("total_paise", internal_row.get("amount_paise"))
        provider_amount = provider_row.get("amount_paise", provider_row.get("total_paise"))
        amount_mismatch = (
            not _is_integer(internal_amount)
            or not _is_integer(provider_amount)
            or internal_amount != provider_amount
        )
        status_mismatch = (
            "status" not in internal_row
            or "status" not in provider_row
            or internal_row.get("status") != provider_row.get("status")
        )

        if amount_mismatch:
            report["amount_mismatches"].append(key)
        if status_mismatch:
            report["status_mismatches"].append(key)
        if not amount_mismatch and not status_mismatch:
            report["matched"].append(key)

    return report
