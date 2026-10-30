"""Starter order lifecycle and refund service; all data is synthetic."""
import csv
import io
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    if not isinstance(order, dict):
        return {}
    if not isinstance(event, dict):
        return deepcopy(order)

    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    event_id = event.get("event_id")
    # Idempotency check: replay of already processed event must not alter state
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out

    kind = event.get("type")

    if kind == "payment_confirmed":
        if out.get("payment_status") != "REFUNDED":
            out["payment_status"] = "PAID"
            # If rejected/cancelled prior to payment confirmation, record full refund due
            if out.get("status") in ("REJECTED", "CANCELLED") and out.get("refund_due_paise", 0) == 0:
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
        status = out.get("status")
        payment_status = out.get("payment_status")
        due = out.get("refund_due_paise", 0)
        refunded = out.get("refunded_paise", 0)

        # Validate refund eligibility: order must be cancelled or rejected, paid, and have refund due
        if status in ("REJECTED", "CANCELLED") and payment_status == "PAID" and due > 0:
            amount = event.get("amount_paise")
            # Refund amounts must be positive integer paise (excluding boolean)
            if isinstance(amount, int) and not isinstance(amount, bool) and amount > 0:
                remaining_due = due - refunded
                if amount <= remaining_due:
                    out["refunded_paise"] = refunded + amount
                    if out["refunded_paise"] == due:
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
    if not isinstance(internal, list) or not isinstance(provider, list):
        return report

    left = {}
    for r in internal:
        if isinstance(r, dict) and r.get("order_id") is not None:
            left[r.get("order_id")] = r

    right = {}
    for r in provider:
        if isinstance(r, dict) and r.get("order_id") is not None:
            right[r.get("order_id")] = r

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            a_amount = a.get("amount_paise") if a.get("amount_paise") is not None else a.get("total_paise")
            b_amount = b.get("amount_paise") if b.get("amount_paise") is not None else b.get("total_paise")
            a_status = a.get("status")
            b_status = b.get("status")

            amount_diff = (a_amount != b_amount)
            status_diff = (a_status != b_status)

            if amount_diff:
                report["amount_mismatches"].append(key)
            if status_diff:
                report["status_mismatches"].append(key)
            if not amount_diff and not status_diff:
                report["matched"].append(key)

    return report


def export_awaiting_refund_csv(orders: list[dict], filepath: str | None = None) -> str:
    """Export orders awaiting refund (refund_due_paise > refunded_paise) to CSV format.

    Returns the CSV string, and optionally writes it to filepath if provided.
    """
    headers = [
        "order_id",
        "total_paise",
        "status",
        "payment_status",
        "refund_due_paise",
        "refunded_paise",
        "outstanding_refund_paise",
    ]

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)

    if isinstance(orders, list):
        valid_orders = [o for o in orders if isinstance(o, dict) and o.get("order_id") is not None]
        for order in sorted(valid_orders, key=lambda x: str(x.get("order_id", ""))):
            due = order.get("refund_due_paise", 0) or 0
            refunded = order.get("refunded_paise", 0) or 0
            if due > refunded:
                outstanding = due - refunded
                writer.writerow([
                    order.get("order_id"),
                    order.get("total_paise", 0),
                    order.get("status", ""),
                    order.get("payment_status", ""),
                    due,
                    refunded,
                    outstanding,
                ])

    csv_content = output.getvalue()
    if filepath:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)

    return csv_content
