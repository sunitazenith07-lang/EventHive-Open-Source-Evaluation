"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def _is_strict_int(val) -> bool:
    """Return True if val is an int and strictly not a boolean."""
    return isinstance(val, int) and not isinstance(val, bool)


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
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

    event_id = event.get("event_id")
    is_valid_event_id = (
        event_id is not None
        and not isinstance(event_id, bool)
        and event_id != ""
    )

    # Idempotency check: duplicate events must not alter state a second time
    if is_valid_event_id and event_id in out["processed_event_ids"]:
        return out

    kind = event.get("type")

    if kind == "payment_confirmed":
        if out.get("payment_status") == "UNPAID":
            out["payment_status"] = "PAID"
            # If already rejected or cancelled prior to payment confirmation, record full refund due
            if out.get("status") in ("REJECTED", "CANCELLED"):
                total = out.get("total_paise", 0)
                if _is_strict_int(total) and total > 0:
                    out["refund_due_paise"] = total

    elif kind == "restaurant_accepted" and out.get("status") == "PLACED":
        out["status"] = "ACCEPTED"

    elif kind == "restaurant_rejected" and out.get("status") == "PLACED":
        out["status"] = "REJECTED"
        if out.get("payment_status") == "PAID":
            total = out.get("total_paise", 0)
            if _is_strict_int(total) and total > 0:
                out["refund_due_paise"] = total

    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out.get("payment_status") == "PAID":
            total = out.get("total_paise", 0)
            if _is_strict_int(total) and total > 0:
                out["refund_due_paise"] = total

    elif kind == "dispatch_started" and out.get("status") == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"

    elif kind == "order_delivered" and out.get("status") == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"

    elif kind == "refund_processed":
        # Eligibility: order must be cancelled or rejected, previously paid, with positive refund due
        is_eligible = (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out.get("payment_status") == "PAID"
            and _is_strict_int(out.get("refund_due_paise"))
            and out["refund_due_paise"] > 0
        )

        amount = event.get("amount_paise")
        is_valid_amount = _is_strict_int(amount) and amount > 0

        current_refunded = (
            out["refunded_paise"]
            if _is_strict_int(out.get("refunded_paise"))
            else 0
        )
        remaining_due = (
            out["refund_due_paise"] - current_refunded
            if is_eligible
            else 0
        )

        # Refund cannot exceed remaining amount due
        if is_eligible and is_valid_amount and amount <= remaining_due:
            out["refunded_paise"] = current_refunded + amount
            if out["refunded_paise"] >= out["refund_due_paise"]:
                out["payment_status"] = "REFUNDED"
            else:
                out["payment_status"] = "PAID"

    if is_valid_event_id:
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

    if not isinstance(internal, list):
        internal = []
    if not isinstance(provider, list):
        provider = []

    def _clean_records(records):
        d = {}
        for r in records:
            if isinstance(r, dict):
                oid = r.get("order_id")
                if oid is not None and not isinstance(oid, bool) and str(oid).strip() != "":
                    d[oid] = r
        return d

    left = _clean_records(internal)
    right = _clean_records(provider)

    def _get_amount(r):
        return r.get("amount_paise") if "amount_paise" in r else r.get("total_paise")

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a, b = left[key], right[key]
            amt_a = _get_amount(a)
            amt_b = _get_amount(b)
            status_a = a.get("status")
            status_b = b.get("status")

            amt_mismatch = (amt_a != amt_b)
            status_mismatch = (status_a != status_b)

            if amt_mismatch:
                report["amount_mismatches"].append(key)
            if status_mismatch:
                report["status_mismatches"].append(key)
            if not amt_mismatch and not status_mismatch:
                report["matched"].append(key)

    return report


def summarize_orders_by_state(orders: list[dict]) -> dict:
    """Count orders by status and return a dictionary sorted by status name."""
    if not isinstance(orders, list):
        return {}
    counts = {}
    for r in orders:
        if isinstance(r, dict):
            st = r.get("status")
            if st is not None and not isinstance(st, bool) and str(st).strip() != "":
                st_str = str(st)
                counts[st_str] = counts.get(st_str, 0) + 1
    return dict(sorted(counts.items()))
