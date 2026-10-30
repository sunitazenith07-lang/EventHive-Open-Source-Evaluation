"""Synthetic records for local demo only."""
from models import new_order


def sample_orders():
    return [new_order("ORD-101", 45900), new_order("ORD-102", 129900, "ACCEPTED"),
            new_order("ORD-103", 89900, "OUT_FOR_DELIVERY")]


def sample_provider_orders():
    return [{"order_id":"ORD-101","amount_paise":45900,"status":"PLACED"},
            {"order_id":"ORD-102","amount_paise":129900,"status":"CANCELLED"},
            {"order_id":"ORD-104","amount_paise":19900,"status":"DELIVERED"}]
