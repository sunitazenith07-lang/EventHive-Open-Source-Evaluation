"""Order lifecycle and refund service; all data is synthetic.

Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
refunded_paise, processed_event_ids. All money is integer paise.
"""
from copy import deepcopy

REFUNDABLE_STATUSES = ("REJECTED", "CANCELLED")


def _is_valid_id(value) -> bool:
    """An id is a non-empty string or a real integer (bool is not an id)."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, str) and value != "")


def _is_valid_amount(value) -> bool:
    """Refund amounts are positive integer paise; bool is an int in Python, so exclude it."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _mark_refund_due(order: dict) -> None:
    """A paid order that is rejected or cancelled owes the customer its full total."""
    if order["payment_status"] == "PAID":
        order["refund_due_paise"] = order.get("total_paise", 0)


def _apply_refund(order: dict, amount) -> None:
    """Apply one refund notification, or leave the order untouched if it is unsafe."""
    if not _is_valid_amount(amount):
        return
    if order.get("status") not in REFUNDABLE_STATUSES or order["payment_status"] != "PAID":
        return
    outstanding = order["refund_due_paise"] - order["refunded_paise"]
    if amount > outstanding:
        return
    order["refunded_paise"] += amount
    if order["refunded_paise"] == order["refund_due_paise"]:
        order["payment_status"] = "REFUNDED"


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order; the input order is never mutated."""
    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")

    # Idempotency: ignore events with no usable id, and events already seen.
    if not _is_valid_id(event_id) or event_id in out["processed_event_ids"]:
        return out
    out["processed_event_ids"].append(event_id)

    status = out.get("status")
    if kind == "payment_confirmed":
        # Only UNPAID -> PAID; a late confirmation must not undo a REFUNDED order.
        if out["payment_status"] == "UNPAID":
            out["payment_status"] = "PAID"
            if status in REFUNDABLE_STATUSES:
                _mark_refund_due(out)  # money arrived for an already dead order
    elif kind == "restaurant_accepted" and status == "PLACED":
        out["status"] = "ACCEPTED"
    elif kind == "restaurant_rejected" and status == "PLACED":
        out["status"] = "REJECTED"
        _mark_refund_due(out)
    elif kind == "cancel_requested" and status in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        _mark_refund_due(out)
    elif kind == "dispatch_started" and status == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"
    elif kind == "order_delivered" and status == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"
    elif kind == "refund_processed":
        _apply_refund(out, event.get("amount_paise"))
    # Any other event type (or invalid transition) leaves the order unchanged.

    return out


def _index_by_order_id(records) -> dict:
    """Map order_id -> record, skipping rows that are not dicts or lack a usable id.

    If an id appears twice, the last record wins (same as the starter code).
    """
    index = {}
    for record in records or []:
        if isinstance(record, dict) and _is_valid_id(record.get("order_id")):
            index[record["order_id"]] = record
    return index


def _amount(record: dict):
    """Prefer amount_paise; fall back to total_paise (the key new_order() uses)."""
    if "amount_paise" in record:
        return record["amount_paise"]
    return record.get("total_paise")


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id.

    Amount and status are checked independently, so an order that differs in
    both appears in both mismatch lists. 'matched' means neither differs.
    Output lists are sorted by id (as strings) so results are deterministic.
    """
    left = _index_by_order_id(internal)
    right = _index_by_order_id(provider)
    report = {"matched": [], "missing_from_provider": [], "missing_from_internal": [],
              "amount_mismatches": [], "status_mismatches": []}
    for key in sorted(set(left) | set(right), key=str):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amount_differs = _amount(a) != _amount(b)
            status_differs = a.get("status") != b.get("status")
            if amount_differs:
                report["amount_mismatches"].append(key)
            if status_differs:
                report["status_mismatches"].append(key)
            if not amount_differs and not status_differs:
                report["matched"].append(key)
    return report