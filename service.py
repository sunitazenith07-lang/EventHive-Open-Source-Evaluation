"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out = deepcopy(order) if isinstance(order, dict) else {}
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")

    # Idempotency check: replay of an already processed event must not alter state
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    if kind == "payment_confirmed":
        if out.get("payment_status") != "REFUNDED":
            out["payment_status"] = "PAID"
            if out.get("status") in ("REJECTED", "CANCELLED"):
                out["refund_due_paise"] = out.get("total_paise", 0)
    elif kind == "restaurant_accepted" and out.get("status") == "PLACED":
        out["status"] = "ACCEPTED"
    elif kind == "restaurant_rejected" and out.get("status") == "PLACED":
        out["status"] = "REJECTED"
        if out.get("payment_status") == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)
    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out.get("payment_status") == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)
    elif kind == "dispatch_started" and out.get("status") == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"
    elif kind == "order_delivered" and out.get("status") == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"
    elif kind == "refund_processed":
        # Validate eligibility: cancelled/rejected and paid with positive refund due
        if (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
            and out.get("refund_due_paise", 0) > 0
        ):
            amount = event.get("amount_paise")
            # Refund amounts must be positive integers (excluding bools)
            if isinstance(amount, int) and not isinstance(amount, bool) and amount > 0:
                outstanding = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)
                if amount <= outstanding:
                    out["refunded_paise"] = out.get("refunded_paise", 0) + amount
                    if out["refunded_paise"] == out.get("refund_due_paise", 0):
                        out["payment_status"] = "REFUNDED"

    if event_id is not None:
        out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }
    if internal is None:
        internal = []
    if provider is None:
        provider = []

    left = {
        r.get("order_id"): r
        for r in internal
        if isinstance(r, dict) and r.get("order_id") is not None
    }
    right = {
        r.get("order_id"): r
        for r in provider
        if isinstance(r, dict) and r.get("order_id") is not None
    }

    def _get_amount(record: dict):
        if "amount_paise" in record:
            return record.get("amount_paise")
        return record.get("total_paise")

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amount_a = _get_amount(a)
            amount_b = _get_amount(b)
            status_a = a.get("status")
            status_b = b.get("status")

            has_amount_mismatch = (amount_a != amount_b)
            has_status_mismatch = (status_a != status_b)

            if has_amount_mismatch:
                report["amount_mismatches"].append(key)
            if has_status_mismatch:
                report["status_mismatches"].append(key)
            if not has_amount_mismatch and not has_status_mismatch:
                report["matched"].append(key)

    return report


def export_awaiting_refund_csv(orders: list[dict]) -> str:
    """Generate a CSV report of orders awaiting refunds (stretch feature).

    An order is awaiting refund if it is paid, in REJECTED or CANCELLED status,
    and has outstanding refundable amount (refund_due_paise > refunded_paise).

    Returns a CSV formatted string with headers:
    order_id,status,payment_status,total_paise,refund_due_paise,refunded_paise,outstanding_paise
    """
    lines = [
        "order_id,status,payment_status,total_paise,refund_due_paise,refunded_paise,outstanding_paise"
    ]
    for o in orders:
        if not isinstance(o, dict):
            continue
        due = o.get("refund_due_paise", 0)
        refunded = o.get("refunded_paise", 0)
        outstanding = due - refunded
        if (
            outstanding > 0
            and o.get("payment_status") == "PAID"
            and o.get("status") in ("CANCELLED", "REJECTED")
        ):
            oid = o.get("order_id", "")
            status = o.get("status", "")
            pay_status = o.get("payment_status", "")
            total = o.get("total_paise", 0)
            lines.append(f"{oid},{status},{pay_status},{total},{due},{refunded},{outstanding}")
    return "\n".join(lines)
