"""Pure offline order lifecycle and refund reconciliation."""
from copy import deepcopy


TRANSITIONS = {
    "restaurant_accepted": {"PLACED": "ACCEPTED"},
    "restaurant_rejected": {"PLACED": "REJECTED"},
    "cancel_requested": {"PLACED": "CANCELLED", "ACCEPTED": "CANCELLED"},
    "dispatch_started": {"ACCEPTED": "OUT_FOR_DELIVERY"},
    "order_delivered": {"OUT_FOR_DELIVERY": "DELIVERED"},
}
ELIGIBLE = ("CANCELLED", "REJECTED")


def _identifier(value):
    return isinstance(value, str) and bool(value.strip())


def _paise(value):
    return type(value) is int and value >= 0


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an independent copy; malformed or misrouted events are no-ops.

    IDs are scoped to one order. Recognized, well-formed events are consumed
    even if their transition is disallowed. There is no automatic retry queue.
    """
    out = deepcopy(order)
    if not isinstance(order, dict) or not isinstance(event, dict):
        return out
    event_id, kind = event.get("event_id"), event.get("type")
    if not _identifier(order.get("order_id")) or not _identifier(event_id):
        return out
    if "order_id" in event and event["order_id"] != order["order_id"]:
        return out
    if not isinstance(kind, str) or kind not in (*TRANSITIONS, "payment_confirmed", "refund_processed"):
        return out
    history = order.get("processed_event_ids", [])
    total = order.get("total_paise")
    due, refunded = order.get("refund_due_paise", 0), order.get("refunded_paise", 0)
    payment = order.get("payment_status", "UNPAID")
    status = order.get("status")
    if (not isinstance(history, list) or any(not _identifier(i) for i in history)
            or event_id in history or not all(_paise(n) for n in (total, due, refunded))
            or not 0 <= refunded <= due <= total
            or payment not in ("UNPAID", "PAID", "REFUNDED")
            or status not in ("PLACED", "ACCEPTED", "REJECTED", "CANCELLED", "OUT_FOR_DELIVERY", "DELIVERED")):
        return out
    if kind == "refund_processed":
        amount = event.get("amount_paise")
        if type(amount) is not int or amount <= 0:
            return out
        if status in ELIGIBLE and payment == "PAID" and amount <= due - refunded:
            refunded += amount
            if refunded == due:
                payment = "REFUNDED"
    elif kind == "payment_confirmed":
        # A distinct late payment notification must not reopen a completed refund.
        if payment == "UNPAID":
            payment = "PAID"
        if status in ELIGIBLE and payment == "PAID":
            due = total
    else:
        status = TRANSITIONS[kind].get(status, status)
        if status in ELIGIBLE and payment == "PAID":
            due = total
    out.update(status=status, payment_status=payment, refund_due_paise=due,
               refunded_paise=refunded, processed_event_ids=[*history, event_id])
    return out


def _index(rows):
    """Skip unidentifiable rows; reject conflicting duplicates explicitly."""
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or not _identifier(row.get("order_id")):
            continue
        key = row["order_id"]
        if key in indexed and indexed[key] != row:
            raise ValueError(f"Conflicting records for order {key}")
        indexed[key] = row
    return indexed


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare by ID, independently reporting amount and status differences.

    Internal order records may use total_paise; summaries use amount_paise.
    Missing/invalid comparison fields are mismatches, never false matches.
    """
    left, right = _index(internal), _index(provider)
    report = {"matched": [], "missing_from_provider": [], "missing_from_internal": [],
              "amount_mismatches": [], "status_mismatches": []}
    for key in sorted(left.keys() | right.keys()):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amount_a = a.get("amount_paise", a.get("total_paise"))
            amount_b = b.get("amount_paise", b.get("total_paise"))
            amounts_match = _paise(amount_a) and _paise(amount_b) and amount_a == amount_b
            statuses_match = (_identifier(a.get("status")) and _identifier(b.get("status"))
                              and a["status"] == b["status"])
            if not amounts_match:
                report["amount_mismatches"].append(key)
            if not statuses_match:
                report["status_mismatches"].append(key)
            if amounts_match and statuses_match:
                report["matched"].append(key)
    return report
