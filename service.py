"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out=deepcopy(order)
    # Reject malformed order or event structures safely.
    if not isinstance(out, dict):
        return out
    if not isinstance(event, dict):
        return out
    # Initialize expected order fields.
    out.setdefault("payment_status", "UNPAID")
    out.setdefault("refund_due_paise", 0)
    out.setdefault("refunded_paise", 0)
    out.setdefault("processed_event_ids", [])

    event_id = event.get("event_id")
    kind = event.get("type")
    # Allow only supported event types.
    valid_event_types = {
        "payment_confirmed",
        "restaurant_accepted",
        "restaurant_rejected",
        "cancel_requested",
        "dispatch_started",
        "order_delivered",
        "refund_processed",
    }

    if not isinstance(kind, str) or kind not in valid_event_types:
        return out

    # Validate event identifiers.
    if not isinstance(event_id, str) or not event_id.strip():
        return out
     # Validate the existing event history.
    if not isinstance(out["processed_event_ids"], list):
        return out
    # Ignore duplicate event notifications.
    if event_id in out["processed_event_ids"]:
        return out

    # Validate required refund payload data.
    if kind == "refund_processed":
        amount = event.get("amount_paise")

        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount <= 0
        ):
            return out


    # Deliberate starter defects: duplicate and invalid refund events are not
    # fully protected, and some transitions need tighter validation.
    if kind=="payment_confirmed":
        # A completed  refund must not revert to PAID
        if out.get("payment_status") != "REFUNDED":
            out["payment_status"] = "PAID"

            # A late payment for an already cancelled or rejected
            # order creates a full refund obligation.
            if out.get("status") in ("CANCELLED", "REJECTED"):
                out["refund_due_paise"]= out.get("total_paise",0)
    elif kind=="restaurant_accepted" and out.get("status")=="PLACED":
        out["status"]="ACCEPTED"
    elif kind=="restaurant_rejected" and out.get("status")=="PLACED":
        out["status"]="REJECTED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="cancel_requested" and out.get("status") in ("PLACED","ACCEPTED"):
        out["status"]="CANCELLED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="dispatch_started" and out.get("status")=="ACCEPTED":
        out["status"]="OUT_FOR_DELIVERY"
    elif kind=="order_delivered" and out.get("status")=="OUT_FOR_DELIVERY":
        out["status"]="DELIVERED"
    elif kind=="refund_processed":
        amount= event.get("amount_paise")
        refund_due = out.get("refund_due_paise")
        refunded = out.get("refunded_paise")
        # Check refund eligiblity.
        eligible = (
            out.get("status") in ("CANCELLED", "REJECTED") # checking if the order is cancelled or rejected
            and out.get("payment_status") == "PAID" # customer actually paid
            # both conditions should be true to proceed
        )
        # Validate existing refund values

        valid_balance=(
            isinstance(refund_due,int)
            and not isinstance(refund_due, bool)
            and refund_due > 0
            and isinstance(refunded, int)
            and not isinstance(refunded, bool)
            and 0<= refunded <=refund_due
        )
        # refund must be a positive  int not a bool
        valid_amount=(
            isinstance(amount,int)
            and not isinstance(amount, bool)
            and amount>0
        )
        if eligible and valid_balance and valid_amount:
            outstanding= refund_due - refunded
            # reject the entire  refund if it exceeds the balance
            if amount<=outstanding:
                out["refunded_paise"]= refunded + amount
                if out["refunded_paise"]==refund_due:
                    out ["payment_status"] = "REFUNDED"
    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
     # Build an index while detecting duplicate order IDs.
    def index_by_order_id(records):
        indexed = {}
        for record in records:
            # Each reconciliation record must be a dictionary.
            if not isinstance(record,dict):
                raise ValueError("Invalid reconciliation record")
            # Validate the order identifier.
            order_id = record.get("order_id")
            if not isinstance(order_id,str) or not order_id.strip():
                raise ValueError("Invalid order_id")
            # Reject duplicate order identifiers.
            if order_id in indexed:
                raise ValueError(f"Duplicate order_id: {order_id}")
            indexed[order_id] = record
        return indexed
    left= index_by_order_id(internal)
    right= index_by_order_id(provider)
    report={"matched":[],"missing_from_provider":[],"missing_from_internal":[],
            "amount_mismatches":[],"status_mismatches":[]}
    def is_valid_paise(value):
        return(
            isinstance(value,int)
            and not isinstance(value,bool)
            and value>=0
        )
    for key in sorted(set(left)|set(right),key=lambda x:str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a,b=left[key],right[key]

            #Normalize internal and provider amount fields.
            internal_amount = a.get("total_paise")
            if internal_amount is None:
                internal_amount = a.get("amount_paise")
            provider_amount = b.get("amount_paise")
            if provider_amount is None:
                provider_amount = b.get("total_paise")
            # Validate both monetary amounts before comparison.
            amount_matches=(
                is_valid_paise(internal_amount)
                and is_valid_paise(provider_amount)
                and internal_amount == provider_amount
            )

            # Compare statuses independently.
            internal_status= a.get("status")
            provider_status= b.get("status")
            status_matches = (
                 isinstance(internal_status, str)
                and bool(internal_status.strip())
                and isinstance(provider_status, str)
                and bool(provider_status.strip())
                and internal_status == provider_status
            )
            if not amount_matches:
                report["amount_mismatches"].append(key)

            if not status_matches:
                report["status_mismatches"].append(key)

            if amount_matches and status_matches:
                report["matched"].append(key)


    return report
