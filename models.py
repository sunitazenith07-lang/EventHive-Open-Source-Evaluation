"""Helpers for synthetic food-delivery order records."""


def new_order(order_id: str, total_paise: int, status: str="PLACED") -> dict:
    return {"order_id":order_id,"total_paise":total_paise,"status":status,
            "payment_status":"UNPAID","refund_due_paise":0,"refunded_paise":0,
            "processed_event_ids":[]}
