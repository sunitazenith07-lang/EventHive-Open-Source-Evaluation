"""Order lifecycle, refund and reconciliation service; all data is synthetic.

Core rules (see STUDENT_PROBLEM_STATEMENT.md):

* Every event needs a non-empty string ``event_id``. An event whose id is
  already in ``processed_event_ids`` is a replay and changes nothing.
* Only the transitions listed in ``TRANSITIONS`` change ``status``. Anything
  else (for example a cancellation after dispatch) is rejected and leaves the
  order untouched.
* Money is integer paise. A refund must be a positive ``int`` (``bool`` is not
  accepted), the order must be CANCELLED or REJECTED with payment_status PAID,
  and the amount must not exceed ``refund_due_paise - refunded_paise``.
* ``payment_status`` becomes REFUNDED only when ``refunded_paise`` reaches
  ``refund_due_paise`` exactly.

Rejected events are *not* recorded in ``processed_event_ids``: if a refund
notification arrives before the order becomes eligible, a later redelivery of
the same event can still be applied once.
"""
from copy import deepcopy

# event type -> (statuses it may be applied from, status it moves the order to)
TRANSITIONS = {
    "restaurant_accepted": (("PLACED",), "ACCEPTED"),
    "restaurant_rejected": (("PLACED",), "REJECTED"),
    "cancel_requested": (("PLACED", "ACCEPTED"), "CANCELLED"),
    "dispatch_started": (("ACCEPTED",), "OUT_FOR_DELIVERY"),
    "order_delivered": (("OUT_FOR_DELIVERY",), "DELIVERED"),
}
EVENT_TYPES = frozenset(TRANSITIONS) | {"payment_confirmed", "refund_processed"}
REFUNDABLE_STATUSES = ("CANCELLED", "REJECTED")

# Outcome codes returned by evaluate_order_event.
APPLIED = "applied"
DUPLICATE = "duplicate_event"


def _is_paise(value) -> bool:
    """True for a real integer amount. bool is an int subclass, so exclude it."""
    return isinstance(value, int) and not isinstance(value, bool)


def _with_defaults(order: dict) -> dict:
    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])
    return out


def _full_refund_due(order: dict) -> int:
    total = order.get("total_paise", 0)
    return total if _is_paise(total) and total > 0 else 0


def evaluate_order_event(order: dict, event: dict) -> tuple[dict, str]:
    """Apply one event to a copy of ``order``.

    Returns ``(updated_order, outcome)``. ``outcome`` is ``APPLIED``,
    ``DUPLICATE`` or a short reason the event was rejected. The input order is
    never mutated, and for any outcome other than ``APPLIED`` the returned
    order is identical in value to the input (plus default keys).
    """
    out = _with_defaults(order)

    if not isinstance(event, dict):
        return out, "malformed_event"
    event_id = event.get("event_id")
    kind = event.get("type")
    if not isinstance(event_id, str) or not event_id:
        return out, "missing_event_id"
    if event_id in out["processed_event_ids"]:
        return out, DUPLICATE
    if not isinstance(kind, str) or kind not in EVENT_TYPES:
        return out, "unknown_event_type"
    event_order = event.get("order_id")
    if event_order is not None and event_order != out.get("order_id"):
        return out, "order_id_mismatch"

    status = out.get("status")

    if kind == "payment_confirmed":
        if out["payment_status"] != "UNPAID":
            return out, "already_paid"
        out["payment_status"] = "PAID"
        # A payment that lands after a cancel/reject is money we must return.
        if status in REFUNDABLE_STATUSES:
            out["refund_due_paise"] = _full_refund_due(out)

    elif kind == "refund_processed":
        amount = event.get("amount_paise")
        if not _is_paise(amount) or amount <= 0:
            return out, "invalid_refund_amount"
        if status not in REFUNDABLE_STATUSES or out["payment_status"] != "PAID":
            return out, "refund_not_eligible"
        outstanding = out["refund_due_paise"] - out["refunded_paise"]
        if outstanding <= 0:
            return out, "refund_not_eligible"
        if amount > outstanding:
            return out, "refund_exceeds_outstanding"
        out["refunded_paise"] += amount
        if out["refunded_paise"] == out["refund_due_paise"]:
            out["payment_status"] = "REFUNDED"

    else:
        allowed_from, target = TRANSITIONS[kind]
        if status not in allowed_from:
            return out, "invalid_transition"
        out["status"] = target
        if target in REFUNDABLE_STATUSES and out["payment_status"] == "PAID":
            out["refund_due_paise"] = _full_refund_due(out)

    out["processed_event_ids"].append(event_id)
    return out, APPLIED


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    return evaluate_order_event(order, event)[0]


def process_events(orders: list[dict], events: list[dict]) -> tuple[dict, list[dict]]:
    """Apply a stream of events to a set of orders, in input order.

    Returns ``(orders_by_id, rejected)`` where ``rejected`` lists every event
    that did not change state, with its position in the input and a reason.
    Events for unknown order ids are rejected rather than creating orders.
    """
    state = {}
    for order in orders or []:
        if isinstance(order, dict) and isinstance(order.get("order_id"), str):
            state.setdefault(order["order_id"], _with_defaults(order))

    rejected = []
    for index, event in enumerate(events or []):
        order_id = event.get("order_id") if isinstance(event, dict) else None
        if order_id is None:
            reason = "missing_order_id" if isinstance(event, dict) else "malformed_event"
        elif order_id not in state:
            reason = "unknown_order_id"
        else:
            state[order_id], reason = evaluate_order_event(state[order_id], event)
            if reason == APPLIED:
                continue
        event_id = event.get("event_id") if isinstance(event, dict) else None
        rejected.append({"index": index, "event_id": event_id,
                         "order_id": order_id, "reason": reason})
    return state, rejected


def _index_records(rows, side: str, invalid: list) -> dict:
    """Key rows by order_id; malformed rows and repeated ids go to ``invalid``."""
    indexed = {}
    for i, row in enumerate(rows or []):
        oid = row.get("order_id") if isinstance(row, dict) else None
        if not isinstance(oid, str) or not oid:
            invalid.append(f"{side}[{i}]: missing order_id")
        elif oid in indexed:
            invalid.append(f"{side}[{i}]: duplicate order_id {oid}")
        else:
            indexed[oid] = row
    return indexed


def _amount(row: dict):
    """Internal orders store total_paise; provider summaries store amount_paise."""
    return row["amount_paise"] if "amount_paise" in row else row.get("total_paise")


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id.

    Every list in the report is sorted by order id, so the result does not
    depend on input order. An order is ``matched`` only when amount, status
    and (if both sides carry it) payment_status all agree; each kind of
    difference is reported in its own list, so one order can appear in more
    than one mismatch list.
    """
    report = {"matched": [], "missing_from_provider": [], "missing_from_internal": [],
              "amount_mismatches": [], "status_mismatches": [],
              "payment_status_mismatches": [], "invalid_records": []}
    left = _index_records(internal, "internal", report["invalid_records"])
    right = _index_records(provider, "provider", report["invalid_records"])

    for key in sorted(set(left) | set(right)):
        if key not in right:
            report["missing_from_provider"].append(key)
            continue
        if key not in left:
            report["missing_from_internal"].append(key)
            continue
        a, b = left[key], right[key]
        clean = True
        if _amount(a) != _amount(b):
            report["amount_mismatches"].append(key)
            clean = False
        if a.get("status") != b.get("status"):
            report["status_mismatches"].append(key)
            clean = False
        if ("payment_status" in a and "payment_status" in b
                and a["payment_status"] != b["payment_status"]):
            report["payment_status_mismatches"].append(key)
            clean = False
        if clean:
            report["matched"].append(key)
    return report
