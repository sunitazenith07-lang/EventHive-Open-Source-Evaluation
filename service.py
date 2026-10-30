
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

    # Deliberate starter defects: duplicate and invalid refund events are not
    # fully protected, and some transitions need tighter validation.

    # Check whether event ID is missing or already processed
    if event_id is None or event_id == "":
        return out

    if event_id in out["processed_event_ids"]:
        return out

    if kind == "payment_confirmed":
        if out["payment_status"] == "UNPAID":
            out["payment_status"] = "PAID"

            if out.get("status") in ("REJECTED", "CANCELLED"):
                out["refund_due_paise"] = out.get("total_paise", 0)

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
        # Bug to find: validate eligibility, positive amount and maximum refund.

        amount = event.get("amount_paise", 0)

        # Refund is allowed only for rejected or cancelled orders
        if out.get("status") not in ("REJECTED", "CANCELLED"):
            return out

        if out["payment_status"] != "PAID":
            return out

        if amount <= 0:
            return out

        if out["refunded_paise"] + amount > out["refund_due_paise"]:
            return out

        out["refunded_paise"] += amount

        if out["refunded_paise"] == out["refund_due_paise"]:
            out["payment_status"] = "REFUNDED"

    else:
        return out

    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""

    left = {}
    right = {}

    # Check for missing order IDs and duplicate order IDs
    for r in internal:
        key = r.get("order_id")

        if key is None:
            raise ValueError("Missing order ID")

        if key in left:
            raise ValueError("Duplicate internal order ID")

        left[key] = r

    for r in provider:
        key = r.get("order_id")

        if key is None:
            raise ValueError("Missing order ID")

        if key in right:
            raise ValueError("Duplicate provider order ID")

        right[key] = r

    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": []
    }

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):

        if key not in right:
            report["missing_from_provider"].append(key)

        elif key not in left:
            report["missing_from_internal"].append(key)

        else:
            a = left[key]
            b = right[key]

            # Check amount mismatch
            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)

            # Check missing amounts
            elif a.get("amount_paise") is None:
                report["amount_mismatches"].append(key)

            # Check status mismatch
            if a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)

            # Add to matched only when both amount and status match
            if (
                a.get("amount_paise") is not None
                and a.get("amount_paise") == b.get("amount_paise")
                and a.get("status") is not None
                and a.get("status") == b.get("status")
            ):
                report["matched"].append(key)

    return report

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

    # Deliberate starter defects: duplicate and invalid refund events are not
    # fully protected, and some transitions need tighter validation.

    # Check whether event ID is missing or already processed
    if event_id is None or event_id == "":
        return out

    if event_id in out["processed_event_ids"]:
        return out

    if kind == "payment_confirmed":
        if out["payment_status"] == "UNPAID":
            out["payment_status"] = "PAID"

            if out.get("status") in ("REJECTED", "CANCELLED"):
                out["refund_due_paise"] = out.get("total_paise", 0)

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
        # Bug to find: validate eligibility, positive amount and maximum refund.

        amount = event.get("amount_paise", 0)

        # Refund is allowed only for rejected or cancelled orders
        if out.get("status") not in ("REJECTED", "CANCELLED"):
            return out

        if out["payment_status"] != "PAID":
            return out

        if type(amount) != int or amount <= 0:
            return out

        if out["refunded_paise"] + amount > out["refund_due_paise"]:
            return out

        out["refunded_paise"] += amount

        if out["refunded_paise"] == out["refund_due_paise"]:
            out["payment_status"] = "REFUNDED"

    else:
        return out

    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""

    left = {}
    right = {}

    # Check for missing order IDs and duplicate order IDs
    for r in internal:
        key = r.get("order_id")

        if key is None:
            raise ValueError("Missing order ID")

        if key in left:
            raise ValueError("Duplicate internal order ID")

        left[key] = r

    for r in provider:
        key = r.get("order_id")

        if key is None:
            raise ValueError("Missing order ID")

        if key in right:
            raise ValueError("Duplicate provider order ID")

        right[key] = r

    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": []
    }

    for key in sorted(set(left) | set(right), key=lambda x: str(x)):

        if key not in right:
            report["missing_from_provider"].append(key)

        elif key not in left:
            report["missing_from_internal"].append(key)

        else:
            a = left[key]
            b = right[key]

            # Check amount mismatch
            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)

            # Check missing amounts
            elif a.get("amount_paise") is None:
                report["amount_mismatches"].append(key)

            # Check status mismatch
            if a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)

            # Add to matched only when both amount and status match
            if (
                a.get("amount_paise") is not None
                and a.get("amount_paise") == b.get("amount_paise")
                and a.get("status") is not None
                and a.get("status") == b.get("status")
            ):
                report["matched"].append(key)

    return report
