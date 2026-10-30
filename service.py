"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy


def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    event_id=event.get("event_id")

    # Avoid applying an event a second time.
    if event_id in order.get("processed_event_ids",[]):
        return deepcopy(order)

    # Do not process an event that has no ID to track.
    if event_id is None:
        return deepcopy(order)

    out=deepcopy(order)
    out.setdefault("payment_status","UNPAID")
    out.setdefault("refund_due_paise",0)
    out.setdefault("refunded_paise",0)
    out.setdefault("processed_event_ids",[])
    kind=event.get("type")

    # Confirm payment for the order.
    if kind=="payment_confirmed":
        out["payment_status"]="PAID"
    # Accept an order only while it is placed.
    elif kind=="restaurant_accepted" and out.get("status")=="PLACED":
        out["status"]="ACCEPTED"
    # Reject an order only while it is placed.
    elif kind=="restaurant_rejected" and out.get("status")=="PLACED":
        out["status"]="REJECTED"
        # Set the full order total as due when payment was already made.
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    # Cancel an order only before it has been dispatched.
    elif kind=="cancel_requested" and out.get("status") in ("PLACED","ACCEPTED"):
        out["status"]="CANCELLED"
        # Set the full order total as due when payment was already made.
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    # Start delivery only after the restaurant accepts the order.
    elif kind=="dispatch_started" and out.get("status")=="ACCEPTED":
        out["status"]="OUT_FOR_DELIVERY"
    # Mark delivery complete only after dispatch has started.
    elif kind=="order_delivered" and out.get("status")=="OUT_FOR_DELIVERY":
        out["status"]="DELIVERED"
    # Process a refund only for an eligible paid order with a valid amount.
    elif kind=="refund_processed":
        amount=event.get("amount_paise")
        refund_due=out.get("refund_due_paise",0)
        refunded=out.get("refunded_paise",0)
        # Check order status, payment, amount type, and refund totals before adding money.
        if (out.get("status") in ("CANCELLED","REJECTED")
                and out.get("payment_status")=="PAID"
                and type(amount)==int and amount>0
                and type(refund_due)==int and type(refunded)==int
                and refund_due>0 and refunded>=0
                and amount<=refund_due-refunded):
            out["refunded_paise"]=refunded+amount
            # Mark payment refunded only when the full due amount has been returned.
            if out["refunded_paise"]==refund_due:
                out["payment_status"]="REFUNDED"

    out["processed_event_ids"].append(event_id)
    return out


def reconcile_orders(internal: list[dict], provider: list[dict]) -> dict:
    """Compare transaction summaries keyed by order_id."""
    left={r.get("order_id"):r for r in internal}
    right={r.get("order_id"):r for r in provider}
    report={"matched":[],"missing_from_provider":[],"missing_from_internal":[],
            "amount_mismatches":[],"status_mismatches":[]}
    for key in sorted(set(left)|set(right),key=lambda x:str(x)):
        if key not in right:
            report["missing_from_provider"].append(key)
        elif key not in left:
            report["missing_from_internal"].append(key)
        else:
            a,b=left[key],right[key]
            # Report amount differences separately.
            if a.get("amount_paise") != b.get("amount_paise"):
                report["amount_mismatches"].append(key)
            # Report status differences separately.
            if a.get("status") != b.get("status"):
                report["status_mismatches"].append(key)
            # Match an order only when both its amount and status agree.
            if (a.get("amount_paise") == b.get("amount_paise")
                    and a.get("status") == b.get("status")):
                report["matched"].append(key)
    return report
