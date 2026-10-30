"""Order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


_EVENT_TYPES = {
    "payment_confirmed",
    "restaurant_accepted",
    "restaurant_rejected",
    "cancel_requested",
    "dispatch_started",
    "order_delivered",
    "refund_processed",
}


def _is_paise_amount(value: object) -> bool:
    """Return whether value is an integer paise amount (excluding bool)."""
    return isinstance(value, int) and not isinstance(value, bool)


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order after applying one valid event.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out = deepcopy(order)
    if not isinstance(out.get("processed_event_ids"), list):
        out["processed_event_ids"] = []
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)

    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")
    if (
        not isinstance(event_id, str)
        or not event_id
        or not isinstance(kind, str)
        or kind not in _EVENT_TYPES
    ):
        return out
    if event_id in out["processed_event_ids"]:
        return out

    status = out.get("status")
    if kind == "payment_confirmed":
        if out["payment_status"] != "REFUNDED":
            out["payment_status"] = "PAID"
            if status in ("CANCELLED", "REJECTED") and out["refund_due_paise"] == 0:
                total = out.get("total_paise")
                if _is_paise_amount(total) and total > 0:
                    out["refund_due_paise"] = total
    elif kind == "restaurant_accepted" and status == "PLACED":
        out["status"] = "ACCEPTED"
    elif kind == "restaurant_rejected" and status == "PLACED":
        out["status"] = "REJECTED"
        if out["payment_status"] == "PAID":
            total = out.get("total_paise")
            if _is_paise_amount(total) and total > 0:
                out["refund_due_paise"] = total
    elif kind == "cancel_requested" and status in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out["payment_status"] == "PAID":
            total = out.get("total_paise")
            if _is_paise_amount(total) and total > 0:
                out["refund_due_paise"] = total
    elif kind == "dispatch_started" and status == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"
    elif kind == "order_delivered" and status == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"
    elif kind == "refund_processed":
        amount = event.get("amount_paise")
        due = out["refund_due_paise"]
        refunded = out["refunded_paise"]
        eligible = (
            status in ("CANCELLED", "REJECTED")
            and out["payment_status"] == "PAID"
            and _is_paise_amount(due)
            and due > 0
            and _is_paise_amount(refunded)
            and 0 <= refunded < due
            and _is_paise_amount(amount)
            and amount > 0
            and amount <= due - refunded
        )
        if eligible:
            out["refunded_paise"] = refunded + amount
            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"

    # Consume recognized events even when their transition is not applicable.
    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left = {r.get("order_id"): r for r in internal if r.get("order_id") is not None}
    right = {r.get("order_id"): r for r in provider if r.get("order_id") is not None}
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }
    for key in sorted(set(left) | set(right), key=lambda x: (type(x).__name__, str(x))):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amount_matches = (
                "amount_paise" in a
                and "amount_paise" in b
                and a["amount_paise"] == b["amount_paise"]
            )
            status_matches = (
                "status" in a and "status" in b and a["status"] == b["status"]
            )
            if not amount_matches:
                report["amount_mismatches"].append(key)
            if not status_matches:
                report["status_mismatches"].append(key)
            if amount_matches and status_matches:
                report["matched"].append(key)
    return report
