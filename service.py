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
    if not isinstance(out["processed_event_ids"], list):
        return out

    if not isinstance(event, dict):
        return out

    event_id = event.get("event_id")
    kind = event.get("type")
    event_types = {
        "payment_confirmed",
        "restaurant_accepted",
        "restaurant_rejected",
        "cancel_requested",
        "dispatch_started",
        "order_delivered",
        "refund_processed",
    }
    if (
        not isinstance(event_id, str)
        or not event_id
        or not isinstance(kind, str)
        or kind not in event_types
    ):
        return out
    if "order_id" in event:
        event_order_id = event["order_id"]
        if (
            not isinstance(event_order_id, str)
            or not event_order_id
            or event_order_id != out.get("order_id")
        ):
            return out
    if event_id in out["processed_event_ids"]:
        return out

    refund_amount = None
    if kind == "refund_processed":
        refund_amount = event.get("amount_paise")
        if type(refund_amount) is not int or refund_amount <= 0:
            return out

    if kind == "payment_confirmed":
        if out["payment_status"] == "UNPAID":
            total = out.get("total_paise")
            if (
                out.get("status") in ("REJECTED", "CANCELLED")
                and (type(total) is not int or total < 0)
            ):
                return out
            out["payment_status"] = "PAID"
            if out.get("status") in ("REJECTED", "CANCELLED"):
                out["refund_due_paise"] = total
    elif kind == "restaurant_accepted" and out.get("status") == "PLACED":
        out["status"] = "ACCEPTED"
    elif kind == "restaurant_rejected" and out.get("status") == "PLACED":
        total = out.get("total_paise")
        if out["payment_status"] == "PAID" and (type(total) is not int or total < 0):
            return out
        out["status"] = "REJECTED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = total
    elif kind == "cancel_requested" and out.get("status") in ("PLACED", "ACCEPTED"):
        total = out.get("total_paise")
        if out["payment_status"] == "PAID" and (type(total) is not int or total < 0):
            return out
        out["status"] = "CANCELLED"
        if out["payment_status"] == "PAID":
            out["refund_due_paise"] = total
    elif kind == "dispatch_started" and out.get("status") == "ACCEPTED":
        out["status"] = "OUT_FOR_DELIVERY"
    elif kind == "order_delivered" and out.get("status") == "OUT_FOR_DELIVERY":
        out["status"] = "DELIVERED"
    elif kind == "refund_processed":
        due = out["refund_due_paise"]
        refunded = out["refunded_paise"]
        if (
            out.get("status") in ("REJECTED", "CANCELLED")
            and out["payment_status"] == "PAID"
            and type(due) is int
            and due >= 0
            and type(refunded) is int
            and 0 <= refunded <= due
            and refund_amount <= due - refunded
        ):
            out["refunded_paise"] = refunded + refund_amount
            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"
        else:
            return out

    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries by order_id.

    Raise ValueError when a record is not a mapping or has an invalid or
    duplicate order ID; malformed amounts and statuses are reported as
    mismatches rather than treated as matches.
    """
    def index_records(records: list[dict], source: str) -> dict:
        indexed = {}
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"{source}[{index}] must be a mapping")
            order_id = record.get("order_id")
            if not isinstance(order_id, str) or not order_id:
                raise ValueError(f"{source}[{index}] must have a non-empty string order_id")
            if order_id in indexed:
                raise ValueError(f"{source} contains duplicate order_id {order_id!r}")
            indexed[order_id] = record
        return indexed

    left = index_records(internal, "internal")
    right = index_records(provider, "provider")
    report = {
        "matched": [],
        "missing_from_provider": [],
        "missing_from_internal": [],
        "amount_mismatches": [],
        "status_mismatches": [],
    }
    for key in sorted(set(left)|set(right),key=lambda x:str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a,b=left[key],right[key]
            internal_amount = a.get("amount_paise", a.get("total_paise"))
            provider_amount = b.get("amount_paise", b.get("total_paise"))
            amount_mismatch = (
                type(internal_amount) is not int
                or internal_amount < 0
                or type(provider_amount) is not int
                or provider_amount < 0
                or internal_amount != provider_amount
            )
            status_mismatch = (
                not isinstance(a.get("status"), str)
                or not a["status"]
                or not isinstance(b.get("status"), str)
                or not b["status"]
                or a["status"] != b["status"]
            )
            if amount_mismatch:
                report["amount_mismatches"].append(key)
            if status_mismatch:
                report["status_mismatches"].append(key)
            if not amount_mismatch and not status_mismatch:
                report["matched"].append(key)
    return report
