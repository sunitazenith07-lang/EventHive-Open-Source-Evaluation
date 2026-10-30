"""Starter order lifecycle and refund service; all data is synthetic."""
from copy import deepcopy

VALID_EVENT_TYPES = {
    'payment_confirmed',
    'restaurant_accepted',
    'restaurant_rejected',
    'cancel_requested',
    'dispatch_started',
    'order_delivered',
    'refund_processed',
}

def apply_order_event(order: dict, event: dict) -> dict:
    """Return an updated copy of order.

    Order keys: order_id, total_paise, status, payment_status, refund_due_paise,
    refunded_paise, processed_event_ids.
    """
    out=deepcopy(order)
    out.setdefault("payment_status","UNPAID")
    out.setdefault("refund_due_paise",0)
    out.setdefault("refunded_paise",0)
    if not isinstance(out.get("processed_event_ids"), list):
        out["processed_event_ids"] = []

    if not isinstance(event, dict):
        return out
    event_id=event.get("event_id")
    kind=event.get("type")

    if not isinstance(event_id, str) or not event_id.strip():
        return out

    if kind not in VALID_EVENT_TYPES:
        return out

    if event_id in out["processed_event_ids"]:
        return out

    
 
 
    if kind=="payment_confirmed":
        out["payment_status"]="PAID"
    elif kind=="restaurant_accepted" and out.get("status")=="PLACED":
        out["status"]="ACCEPTED"
    elif kind=="restaurant_rejected" and out.get("status")=="PLACED":
        out["status"]="REJECTED"
        if out["payment_status"]=="PAID":
            out["refund_due_paise"]=out.get("total_paise",0)
    elif kind=="cancel_requested" and out.get("status") in ("PLACED","ACCEPTED"):
        out["status"]="CANCELLED"
        if out["payment_status"]=="PAID":
            total = out.get('total_paise')
            if type(total) is int and total > 0:
                out['refunded_due_paise'] = total
    elif kind=="dispatch_started" and out.get("status")=="ACCEPTED":
        out["status"]="OUT_FOR_DELIVERY"
    elif kind=="order_delivered" and out.get("status")=="OUT_FOR_DELIVERY":
        out["status"]="DELIVERED"
    elif kind=="refund_processed":
        # Bug to find: validate eligibility, positive amount and maximum refund.
        amount = event.get('amount_paise')
        due = out.get('refund_due_paise')
        refunded = out.get('refunded_paise')

        eligible_status = out.get('status') in ('REJECTED', 'CANCELLED')
        eligible_payment = out.get('payment_status') == 'PAID'

        valid_amount = type(amount) is int and amount > 0

        valid_balance = (
            type(due) is int
            and due > 0
            and type(refunded) is int
            and 0 <= refunded <= due
        )

        if (
            eligible_status
            and eligible_payment
            and valid_balance
            and valid_amount
            and amount <= due - refunded
        ):
            out['refunded_paise'] += amount

            if out["refunded_paise"] == due:
                out["payment_status"] = "REFUNDED"

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
            internal_amount = a.get("total_paise")
            if internal_amount is None:
                internal_amount = a.get("amount_paise")

            provider_amount = b.get("amount_paise")
            if provider_amount is None:
                provider_amount = b.get("total_paise")

            amount_matches = (
                internal_amount is not None
                    and provider_amount is not None
                    and internal_amount == provider_amount
)
            status_matches = a.get('status') == b.get('status')
            if not amount_matches:
                report["amount_mismatches"].append(key)

            if not status_matches:
                report["status_mismatches"].append(key)

            if amount_matches and status_matches:
                report["matched"].append(key)
    return report
