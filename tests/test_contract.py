import pytest
from models import new_order
from service import apply_order_event, reconcile_orders


def event(event_id, kind, **extra):
    return {"event_id":event_id,"type":kind,**extra}


def test_accept_only_when_placed_and_does_not_mutate_input():
    order=new_order("O1",1000)
    updated=apply_order_event(order,event("e1","restaurant_accepted"))
    assert updated["status"]=="ACCEPTED"
    assert order["status"]=="PLACED"


def test_paid_rejected_order_records_full_refund_due():
    order=new_order("O1",1000)
    order["payment_status"]="PAID"
    out=apply_order_event(order,event("e1","restaurant_rejected"))
    assert out["status"]=="REJECTED"
    assert out["refund_due_paise"]==1000


def test_cancel_after_dispatch_is_ignored():
    order=new_order("O1",1000,"OUT_FOR_DELIVERY")
    out=apply_order_event(order,event("e1","cancel_requested"))
    assert out["status"]=="OUT_FOR_DELIVERY"


def test_duplicate_event_is_idempotent():
    order=new_order("O1",1000)
    e=event("e1","payment_confirmed")
    first=apply_order_event(order,e)
    second=apply_order_event(first,e)
    assert second["processed_event_ids"]==["e1"]


def test_refund_requires_eligible_order():
    out=apply_order_event(new_order("O1",1000),event("r1","refund_processed",amount_paise=500))
    assert out["refunded_paise"]==0
    assert out["payment_status"]=="UNPAID"


def test_refund_must_be_positive():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=1000)
    for amount in [0,-10]:
        out=apply_order_event(order,event("r1","refund_processed",amount_paise=amount))
        assert out["refunded_paise"]==0


def test_refund_cannot_exceed_amount_due():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=1000)
    out=apply_order_event(order,event("r1","refund_processed",amount_paise=1200))
    assert out["refunded_paise"]==0


def test_partial_refund_is_not_marked_complete():
    order=new_order("O1",1000,"CANCELLED")
    order.update(payment_status="PAID",refund_due_paise=1000)
    out=apply_order_event(order,event("r1","refund_processed",amount_paise=400))
    assert out["refunded_paise"]==400
    assert out["payment_status"]=="PAID"


def test_delivery_state_flow():
    order=new_order("O1",1000)
    for e in [event("1","restaurant_accepted"),event("2","dispatch_started"),event("3","order_delivered")]:
        order=apply_order_event(order,e)
    assert order["status"]=="DELIVERED"


def test_reconcile_reports_missing_and_amount_difference():
    report=reconcile_orders([{"order_id":"A","amount_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":90,"status":"PLACED"},{"order_id":"B","amount_paise":50,"status":"PLACED"}])
    assert report["amount_mismatches"]==["A"]
    assert report["missing_from_internal"]==["B"]


def test_reconcile_reports_status_difference():
    report=reconcile_orders([{"order_id":"A","amount_paise":100,"status":"PLACED"}],
        [{"order_id":"A","amount_paise":100,"status":"DELIVERED"}])
    assert report["status_mismatches"]==["A"]
    assert report["matched"]==[]


def test_empty_reconciliation():
    assert all(v==[] for v in reconcile_orders([],[]).values())


# Regression: compare internal total_paise with provider amount_paise.
def test_reconcile_internal_total_against_provider_amount():
    internal = [
        {"order_id": "A", "total_paise": 45900, "status": "PLACED"}
    ]
    provider = [
        {"order_id": "A", "amount_paise": 45900, "status": "PLACED"}
    ]

    report = reconcile_orders(internal, provider)

    assert report["matched"] == ["A"]
    assert report["amount_mismatches"] == []
    assert report["status_mismatches"] == []

# Regression: events without IDs must not be mistaken for duplicates.
def test_events_without_event_id_are_processed_independently():
    order = new_order("A", 100)

    after_payment = apply_order_event(
        order, {"type": "payment_confirmed"}
    )

    after_acceptance = apply_order_event(
        after_payment, {"type": "restaurant_accepted"}
    )

    assert after_acceptance["payment_status"] == "PAID"
    assert after_acceptance["status"] == "ACCEPTED"
    assert after_acceptance["processed_event_ids"] == []

# Regression: an unidentifiable refund must not be processed.
def test_refund_without_event_id_is_ignored():
    order = new_order("A", 1000, "CANCELLED")
    order.update(
        payment_status="PAID",
        refund_due_paise=1000
    )

    result = apply_order_event(
        order,
        {"type": "refund_processed", "amount_paise": 400}
    )

    assert result["refunded_paise"] == 0
    assert result["payment_status"] == "PAID"
    assert result["processed_event_ids"] == []

# Regression: report amount and status differences for the same order.
def test_reconcile_reports_both_amount_and_status_mismatches():
    internal = [
        {
            "order_id": "ORD-105",
            "total_paise": 15000,
            "status": "DELIVERED",
        }
    ]

    provider = [
        {
            "order_id": "ORD-105",
            "amount_paise": 12000,
            "status": "CANCELLED",
        }
    ]

    result = reconcile_orders(internal, provider)

    assert result["amount_mismatches"] == ["ORD-105"]
    assert result["status_mismatches"] == ["ORD-105"]
    assert result["matched"] == []

# Regression: use the alternate amount field when the preferred field is None.
def test_reconcile_falls_back_when_preferred_amount_is_none():
    internal = [
        {
            "order_id": "ORD-106",
            "total_paise": None,
            "amount_paise": 15000,
            "status": "PLACED",
        }
    ]

    provider = [
        {
            "order_id": "ORD-106",
            "amount_paise": 15000,
            "status": "PLACED",
        }
    ]

    result = reconcile_orders(internal, provider)

    assert result["matched"] == ["ORD-106"]
    assert result["amount_mismatches"] == []

import pytest


# Regression: duplicate IDs in internal records must be rejected.
def test_reconcile_rejects_duplicate_internal_order_ids():
    internal = [
        {"order_id": "ORD-1", "total_paise": 1000, "status": "PLACED"},
        {"order_id": "ORD-1", "total_paise": 2000, "status": "PLACED"},
    ]

    with pytest.raises(ValueError, match="Duplicate order_id in internal records"):
        reconcile_orders(internal, [])


# Regression: duplicate IDs in provider records must be rejected.
def test_reconcile_rejects_duplicate_provider_order_ids():
    provider = [
        {"order_id": "ORD-1", "amount_paise": 1000, "status": "PLACED"},
        {"order_id": "ORD-1", "amount_paise": 2000, "status": "PLACED"},
    ]

    with pytest.raises(ValueError, match="Duplicate order_id in provider records"):
        reconcile_orders([], provider)