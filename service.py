"""Order lifecycle and refund reconciliation for synthetic, offline records."""
from copy import deepcopy


TRANSITIONS = {
    "restaurant_accepted": {"PLACED": "ACCEPTED"},
    "restaurant_rejected": {"PLACED": "REJECTED"},
    "cancel_requested": {"PLACED": "CANCELLED", "ACCEPTED": "CANCELLED"},
    "dispatch_started": {"ACCEPTED": "OUT_FOR_DELIVERY"},
    "order_delivered": {"OUT_FOR_DELIVERY": "DELIVERED"},
}
EVENT_TYPES = {*TRANSITIONS, "payment_confirmed", "refund_processed"}
REFUNDABLE_STATES = ("CANCELLED", "REJECTED")


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _paise(value: object) -> bool:
    # bool is an int subclass, but is not a monetary amount.
    return type(value) is int and value >= 0


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an independent copy, processing a valid event ID at most once.

    event.order_id is optional for this single-order API; an explicit target
    must match. Malformed envelopes leave the entire order unchanged. Known,
    addressed events are recorded even when their transition/refund is refused,
    so replaying them after the state changes cannot produce a new effect.
    """
    out = deepcopy(order)
    if not isinstance(order, dict) or not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")
    if (
        not _identifier(order.get("order_id"))
        or not _identifier(event_id)
        or not isinstance(kind, str)
        or kind not in EVENT_TYPES
        or ("order_id" in event and event["order_id"] != order["order_id"])
    ):
        return out

    processed = order.get("processed_event_ids", [])
    total = order.get("total_paise")
    due = order.get("refund_due_paise", 0)
    refunded = order.get("refunded_paise", 0)
    if (
        not isinstance(processed, list)
        or not all(_identifier(item) for item in processed)
        or event_id in processed
        or not all(_paise(value) for value in (total, due, refunded))
        or not 0 <= refunded <= due <= total
        or not isinstance(order.get("status"), str)
        or order.get("payment_status", "UNPAID") not in ("UNPAID", "PAID", "REFUNDED")
    ):
        return out

    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    if kind == "payment_confirmed":
        if out["payment_status"] == "UNPAID":
            out["payment_status"] = "PAID"
            # Payment confirmation can arrive after cancellation or rejection.
            if out["status"] in REFUNDABLE_STATES:
                out["refund_due_paise"] = total
    elif kind == "refund_processed":
        amount = event.get("amount_paise")
        if (
            out["status"] in REFUNDABLE_STATES
            and out["payment_status"] == "PAID"
            and _paise(amount)
            and 0 < amount <= due - refunded
        ):
            out["refunded_paise"] += amount
            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"
    else:
        next_status = TRANSITIONS[kind].get(out["status"])
        if next_status is not None:
            out["status"] = next_status
            if next_status in REFUNDABLE_STATES and out["payment_status"] == "PAID":
                out["refund_due_paise"] = total

    out["processed_event_ids"].append(event_id)
    return out


def _index_summaries(records: list[dict], *, use_total: bool) -> dict:
    """Group comparable fields without silently overwriting duplicate IDs.

    Unidentifiable rows are ignored. Invalid fields are represented by None,
    which is always a mismatch. Sets collapse identical duplicate summaries;
    conflicting duplicates remain visible in the corresponding mismatch list.
    """
    index = {}
    for row in records or []:
        if not isinstance(row, dict) or not _identifier(row.get("order_id")):
            continue
        amount = row.get("amount_paise")
        if use_total and "amount_paise" not in row:
            amount = row.get("total_paise")
        if not _paise(amount):
            amount = None
        status = row.get("status")
        if not _identifier(status):
            status = None
        amounts, statuses = index.setdefault(row["order_id"], (set(), set()))
        amounts.add(amount)
        statuses.add(status)
    return index


def _same_field(left: set, right: set) -> bool:
    return len(left) == len(right) == 1 and None not in left | right and left == right


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Report sorted missing IDs and independent amount/status differences.

    Internal records may use total_paise or an explicit amount_paise summary.
    Provider summaries use amount_paise. A match requires valid, unambiguous
    amounts and statuses on both sides. Neither input is modified.
    """
    left = _index_summaries(internal, use_total=True)
    right = _index_summaries(provider, use_total=False)
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }
    for key in sorted(left.keys() | right.keys()):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            amounts_match = _same_field(left[key][0], right[key][0])
            statuses_match = _same_field(left[key][1], right[key][1])
            if not amounts_match:
                report["amount_mismatches"].append(key)
            if not statuses_match:
                report["status_mismatches"].append(key)
            if amounts_match and statuses_match:
                report["matched"].append(key)
    return report
