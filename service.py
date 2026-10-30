"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out = deepcopy(order)
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    event_id = event.get("event_id")
    kind = event.get("type")

    # ── Bug 1 FIX: Idempotency ────────────────────────────────────────────────
    # If we have already processed this exact event_id, return immediately
    # without changing anything. This prevents duplicate events (e.g. from a
    # network retry) from being applied twice.
    if event_id in out["processed_event_ids"]:
        return out

    # ── State-transition logic ────────────────────────────────────────────────
    if kind == "payment_confirmed":
        out["payment_status"] = "PAID"

    elif kind == "restaurant_accepted" and out.get("status") == "PLACED":
        out["status"] = "ACCEPTED"

    elif kind == "restaurant_rejected" and out.get("status") == "PLACED":
        out["status"] = "REJECTED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)

    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        out["status"] = "CANCELLED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = out.get("total_paise", 0)

    elif kind == "dispatch_started" and out.get("status") == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"

    elif kind == "order_delivered" and out.get("status") == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"

    elif kind == "refund_processed":
        # ── Bug 2 FIX: Eligibility check ──────────────────────────────────────
        # Refunds are only valid when:
        #   • The order is in a refundable terminal state (CANCELLED or REJECTED)
        #   • The customer has already paid (payment_status == PAID)
        #   • There is actually an outstanding refund amount (refund_due_paise > 0)
        eligible_statuses = {"CANCELLED", "REJECTED"}
        if (
            out.get("status") not in eligible_statuses
            or out.get("payment_status") != "PAID"
            or out.get("refund_due_paise", 0) <= 0
        ):
            # Not eligible — record the event but change nothing financial
            out["processed_event_ids"].append(event_id)
            return out

        # ── Bug 3 FIX: Amount validation ──────────────────────────────────────
        # amount_paise must be a plain integer (bool is a subclass of int in
        # Python, so we exclude it explicitly), and it must be strictly positive.
        amount = event.get("amount_paise")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            out["processed_event_ids"].append(event_id)
            return out

        # ── Bug 4 FIX: Cap at remaining refundable amount ─────────────────────
        # The total refunded so far plus this new amount must not exceed the
        # outstanding refund due.  Reject the whole event if it would overflow.
        already_refunded = out.get("refunded_paise", 0)
        remaining = out.get("refund_due_paise", 0) - already_refunded
        if amount > remaining:
            out["processed_event_ids"].append(event_id)
            return out

        # All checks passed — apply the refund
        out["refunded_paise"] = already_refunded + amount
        if out["refunded_paise"] >= out.get("refund_due_paise", 0):
            out["payment_status"] = "REFUNDED"

    # Record event as processed (for all recognised events that reach here)
    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left = {r.get("order_id"): r for r in internal}
    right = {r.get("order_id"): r for r in provider}
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
            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)
            # ── Bug 5 FIX: Status mismatch check ──────────────────────────────
            # When amounts agree we must still compare statuses.  Only if both
            # amount AND status match does an order belong in "matched".
            elif a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)
            else:
                report["matched"].append(key)

    return report
