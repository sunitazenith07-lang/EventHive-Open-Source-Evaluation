"""Order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order with the event applied."""
    if not isinstance(order, dict):
        return {}

    out = deepcopy(order)
    out.setdefault("status", "PLACED")
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    if not isinstance(out.get("processed_event_ids"), list):
        out["processed_event_ids"] = []

    if not isinstance(event, dict):
        return out

    # Ignore event if it belongs to a different order
    event_order_id = event.get("order_id")
    if event_order_id is not None and out.get("order_id") is not None and event_order_id != out.get("order_id"):
        return out

    event_id = event.get("event_id")
    # Idempotency: if we already saw this event_id, do nothing
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    kind = event.get("type")

    if kind == "payment_confirmed":
        if out.get("payment_status") != "REFUNDED":
            out["payment_status"] = "PAID"
            # If order was already cancelled or rejected, mark full amount as refund due
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
        # Order must be cancelled or rejected and paid
        status = out.get("status")
        payment_status = out.get("payment_status")
        due = out.get("refund_due_paise", 0)
        refunded = out.get("refunded_paise", 0)
        remaining = due - refunded

        if status in ("REJECTED", "CANCELLED") and payment_status == "PAID" and remaining > 0:
            amount = event.get("amount_paise")
            # Must be integer paise, positive, and <= remaining due amount
            # type() is used instead of isinstance() so booleans like True are not treated as 1
            if type(amount) is int and amount > 0 and amount <= remaining:
                out["refunded_paise"] += amount
                if out["refunded_paise"] >= due:
                    out["payment_status"] = "REFUNDED"

    if event_id is not None and event_id not in out["processed_event_ids"]:
        out["processed_event_ids"].append(event_id)

    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare internal orders and provider orders by order_id."""
    left = {r.get("order_id"): r for r in (internal or []) if isinstance(r, dict) and r.get("order_id") is not None}
    right = {r.get("order_id"): r for r in (provider or []) if isinstance(r, dict) and r.get("order_id") is not None}

    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            # Internal order has total_paise, provider has amount_paise
            a_amount = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
            b_amount = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")
            a_status = a.get("status")
            b_status = b.get("status")

            has_amount_diff = (a_amount != b_amount)
            has_status_diff = (a_status != b_status)

            if has_amount_diff:
                report["amount_mismatches"].append(key)
            if has_status_diff:
                report["status_mismatches"].append(key)
            if not has_amount_diff and not has_status_diff:
                report["matched"].append(key)

    return report


def export_awaiting_refund_csv(orders: list[dict], filepath: str | None = None) -> str:
    """Export orders where refund_due_paise > refunded_paise as CSV."""
    headers = ["order_id", "status", "payment_status", "total_paise", "refund_due_paise", "refunded_paise", "awaiting_refund_paise"]
    lines = [",".join(headers)]

    for o in (orders or []):
        if not isinstance(o, dict):
            continue
        due = o.get("refund_due_paise", 0)
        refunded = o.get("refunded_paise", 0)
        awaiting = due - refunded
        if awaiting > 0:
            oid = str(o.get("order_id", ""))
            status = str(o.get("status", ""))
            pay_status = str(o.get("payment_status", ""))
            total = str(o.get("total_paise", 0))
            lines.append(f"{oid},{status},{pay_status},{total},{due},{refunded},{awaiting}")

    csv_text = "\n".join(lines) + "\n"
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(csv_text)

    return csv_text
