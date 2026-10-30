"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def _is_int_amount(value):
    return isinstance(value, int) and not isinstance(value, bool)


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    if not isinstance(order, dict):
        return order

    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")

    # Idempotency: a replayed, identified event must not change state again.
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    total = out.get("total_paise", 0)

    if kind == "payment_confirmed":
        out["payment_status"] = "PAID"
        # A payment arriving after rejection/cancellation makes the order eligible
        # for a full refund instead of leaving refund_due_paise at zero.
        if out.get("status") in ("REJECTED", "CANCELLED") and out.get("refund_due_paise", 0) == 0:
            out["refund_due_paise"] = total
    elif kind == "restaurant_accepted" and out.get("status") == "PLACED":
        out["status"] = "ACCEPTED"
    elif kind == "restaurant_rejected" and out.get("status") == "PLACED":
        out["status"] = "REJECTED"
        if out.get("payment_status") == "PAID":
            out["refund_due_paise"] = total
    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out.get("payment_status") == "PAID":
            out["refund_due_paise"] = total
    elif kind == "dispatch_started" and out.get("status") == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"
    elif kind == "order_delivered" and out.get("status") == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"
    elif kind == "refund_processed":
        refunded = out.get("refunded_paise", 0)
        due = out.get("refund_due_paise", 0)
        amount = event.get("amount_paise")
        eligible = (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
        )
        if (
            eligible
            and _is_int_amount(amount)
            and amount > 0
            and amount <= due - refunded
        ):
            out["refunded_paise"] = refunded + amount
            if out["refunded_paise"] >= due and due > 0:
                out["payment_status"] = "REFUNDED"

    if event_id is not None:
        out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal, provider) -> dict:
    """Compare transaction summaries keyed by order_id."""
    if not isinstance(internal, list):
        internal = []
    if not isinstance(provider, list):
        provider = []

    def _amount(record):
        if not isinstance(record, dict):
            return None
        if "amount_paise" in record:
            return record.get("amount_paise")
        return record.get("total_paise")

    def _status(record):
        if not isinstance(record, dict):
            return None
        return record.get("status")

    left = {}
    for record in internal:
        if not isinstance(record, dict):
            continue
        key = record.get("order_id")
        if key not in left:
            left[key] = record

    right = {}
    for record in provider:
        if not isinstance(record, dict):
            continue
        key = record.get("order_id")
        if key not in right:
            right[key] = record

    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    for key in sorted(set(left) | set(right), key=lambda value: str(value)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amount_mismatch = _amount(a) != _amount(b)
            status_mismatch = _status(a) != _status(b)
            if amount_mismatch:
                report["amount_mismatches"].append(key)
            if status_mismatch:
                report["status_mismatches"].append(key)
            if not amount_mismatch and not status_mismatch:
                report["matched"].append(key)

    for field in report:
        report[field] = sorted(report[field], key=lambda value: str(value))
    return report
