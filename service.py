"""Pure order lifecycle and reconciliation functions for synthetic, offline data."""
from copy import deepcopy


_ORDER_STATES = {
    "PLACED", "ACCEPTED", "REJECTED", "CANCELLED", "OUT_FOR_DELIVERY", "DELIVERED"
}
_PAYMENT_STATES = {"UNPAID", "PAID", "REFUNDED"}
_REFUNDABLE_STATES = {"CANCELLED", "REJECTED"}
_TRANSITIONS = {
    "restaurant_accepted": {"PLACED": "ACCEPTED"},
    "restaurant_rejected": {"PLACED": "REJECTED"},
    "cancel_requested": {"PLACED": "CANCELLED", "ACCEPTED": "CANCELLED"},
    "dispatch_started": {"ACCEPTED": "OUT_FOR_DELIVERY"},
    "order_delivered": {"OUT_FOR_DELIVERY": "DELIVERED"},
}
_EVENT_TYPES = set(_TRANSITIONS) | {"payment_confirmed", "refund_processed"}


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _paise(value: object) -> bool:
    # bool is a subclass of int in Python, but True is not one paise.
    return type(value) is int and value >= 0


def _valid_order(order: dict) -> bool:
    """Reject unsafe snapshots rather than guessing how to repair their money."""
    total = order.get("total_paise")
    due = order.get("refund_due_paise", 0)
    refunded = order.get("refunded_paise", 0)
    history = order.get("processed_event_ids", [])
    status = order.get("status")
    payment = order.get("payment_status", "UNPAID")
    return (
        _identifier(order.get("order_id"))
        and isinstance(status, str) and status in _ORDER_STATES
        and isinstance(payment, str) and payment in _PAYMENT_STATES
        and all(_paise(value) for value in (total, due, refunded))
        and refunded <= due <= total
        and isinstance(history, list)
        and all(_identifier(value) for value in history)
    )


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an independent updated order; never modify either input.

    Missing/invalid envelopes and unsafe order snapshots are unchanged. An
    optional event order_id must match the supplied order. Known, addressed
    events with a valid ID are consumed once, including disallowed transitions
    and ineligible refunds. A rejected notification cannot become effective on
    replay after circumstances change. Event IDs are scoped to one order.
    """
    if not isinstance(order, dict):
        raise TypeError("order must be a dictionary")
    out = deepcopy(order)
    if not _valid_order(out) or not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")
    if not _identifier(event_id) or not isinstance(kind, str) or kind not in _EVENT_TYPES:
        return out
    if "order_id" in event and event["order_id"] != out["order_id"]:
        return out
    if event_id in out.get("processed_event_ids", []):
        return out

    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    if kind == "payment_confirmed":
        # A delayed or distinct notification must not undo REFUNDED.
        if out["payment_status"] == "UNPAID":
            out["payment_status"] = "PAID"
            if out["status"] in _REFUNDABLE_STATES:
                out["refund_due_paise"] = out["total_paise"]
    elif kind in _TRANSITIONS:
        target = _TRANSITIONS[kind].get(out["status"])
        if target is not None:
            out["status"] = target
            if target in _REFUNDABLE_STATES and out["payment_status"] == "PAID":
                out["refund_due_paise"] = out["total_paise"]
    elif kind == "refund_processed":
        amount = event.get("amount_paise")
        remaining = out["refund_due_paise"] - out["refunded_paise"]
        if (
            out["status"] in _REFUNDABLE_STATES
            and out["payment_status"] == "PAID"
            and _paise(amount) and 0 < amount <= remaining
        ):
            out["refunded_paise"] += amount
            if out["refunded_paise"] == out["refund_due_paise"]:
                out["payment_status"] = "REFUNDED"

    out["processed_event_ids"].append(event_id)
    return out


def _summary_index(records: list[dict], side: str) -> dict:
    """Validate summaries; ambiguous records must never be silently matched."""
    if not isinstance(records, (list, tuple)):
        raise ValueError(f"{side} summaries must be a list or tuple")
    index = {}
    for position, row in enumerate(records):
        if not isinstance(row, dict) or not _identifier(row.get("order_id")):
            raise ValueError(f"{side} record {position}: non-empty order_id required")
        order_id = row["order_id"]
        # Domain orders store total_paise; provider summaries use amount_paise.
        amount = row.get("amount_paise", row.get("total_paise"))
        if not _paise(amount):
            raise ValueError(f"{side} record {position}: integer paise amount required")
        if "amount_paise" in row and "total_paise" in row:
            if not _paise(row["total_paise"]) or row["total_paise"] != amount:
                raise ValueError(f"{side} record {position}: conflicting amount fields")
        status = row.get("status")
        if not _identifier(status):
            raise ValueError(f"{side} record {position}: non-empty status required")
        summary = (amount, status)
        if order_id in index and index[order_id] != summary:
            raise ValueError(f"{side}: conflicting duplicate order_id {order_id!r}")
        index[order_id] = summary
    return index


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare integer amounts and order statuses by ID in deterministic order.

    Exact duplicate summaries collapse. Malformed rows or conflicting duplicate
    IDs raise ValueError without mutating input or returning a misleading partial
    report. A record may appear in both mismatch categories.
    """
    left = _summary_index(internal, "internal")
    right = _summary_index(provider, "provider")
    report = {
        "matched": [], "missing_from_provider": [], "missing_from_internal": [],
        "amount_mismatches": [], "status_mismatches": [],
    }
    for order_id in sorted(left.keys() | right.keys()):
        if order_id not in right:
            report["missing_from_provider"].append(order_id)
        elif order_id not in left:
            report["missing_from_internal"].append(order_id)
        else:
            amount_a, status_a = left[order_id]
            amount_b, status_b = right[order_id]
            if amount_a != amount_b:
                report["amount_mismatches"].append(order_id)
            if status_a != status_b:
                report["status_mismatches"].append(order_id)
            if amount_a == amount_b and status_a == status_b:
                report["matched"].append(order_id)
    return report
