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


def test_reconcile_maps_internal_total_to_provider_amount():
    report = reconcile_orders(
        [{"order_id": "A", "total_paise": 45900, "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 45900, "status": "PLACED"}],
    )

    assert report["matched"] == ["A"]
    assert report["amount_mismatches"] == []
    assert report["status_mismatches"] == []


def test_reconcile_reports_amount_and_status_mismatch_together():
    report = reconcile_orders(
        [{"order_id": "A", "total_paise": 100, "status": "ACCEPTED"}],
        [{"order_id": "A", "amount_paise": 90, "status": "CANCELLED"}],
    )

    assert report["matched"] == []
    assert report["amount_mismatches"] == ["A"]
    assert report["status_mismatches"] == ["A"]


def test_reconcile_does_not_match_when_amount_is_missing():
    report = reconcile_orders(
        [{"order_id": "A", "status": "PLACED"}],
        [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
    )

    assert report["matched"] == []
    assert report["amount_mismatches"] == ["A"]

def test_unhashable_event_types_are_ignored():
    order = new_order("O1", 1000)

    for invalid_type in [[], {}, ["payment_confirmed"], {"type": "payment_confirmed"}]:
        result = apply_order_event(
            order,
            {"event_id": "E1", "type": invalid_type}
        )

        assert result["status"] == "PLACED"
        assert result["payment_status"] == "UNPAID"
        assert result["processed_event_ids"] == []


def test_missing_event_id_is_ignored():
    order = new_order("O1", 1000)

    result = apply_order_event(
        order,
        {"type": "payment_confirmed"}
    )

    assert result["payment_status"] == "UNPAID"
    assert result["processed_event_ids"] == []


def test_duplicate_event_id_with_different_payload_is_ignored():
    order = new_order("O1", 1000)

    first = apply_order_event(
        order,
        {"event_id": "E1", "type": "payment_confirmed"}
    )

    second = apply_order_event(
        first,
        {"event_id": "E1", "type": "restaurant_accepted"}
    )

    assert second["payment_status"] == "PAID"
    assert second["status"] == "PLACED"
    assert second["processed_event_ids"] == ["E1"]


def test_non_dictionary_event_is_ignored():
    order = new_order("O1", 1000)

    for invalid_event in [None, [], "payment_confirmed", 123]:
        result = apply_order_event(order, invalid_event)

        assert result["status"] == "PLACED"
        assert result["payment_status"] == "UNPAID"
        assert result["processed_event_ids"] == []

def test_rejection_then_payment_confirmed_then_refund():
    order = new_order("O-REJ", 3000)
    rejected = apply_order_event(order, event("e1", "restaurant_rejected"))
    assert rejected["status"] == "REJECTED"
    assert rejected["payment_status"] == "UNPAID"
    assert rejected["refund_due_paise"] == 0

    paid = apply_order_event(rejected, event("e2", "payment_confirmed"))
    assert paid["status"] == "REJECTED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 3000

    # Duplicate payment confirmation should be idempotent
    dup_paid = apply_order_event(paid, event("e2", "payment_confirmed"))
    assert dup_paid["refund_due_paise"] == 3000
    assert dup_paid["processed_event_ids"] == ["e1", "e2"]

    # Partial refund
    partial = apply_order_event(paid, event("e3", "refund_processed", amount_paise=1000))
    assert partial["refunded_paise"] == 1000
    assert partial["payment_status"] == "PAID"

    # Remaining refund completes
    completed = apply_order_event(partial, event("e4", "refund_processed", amount_paise=2000))
    assert completed["refunded_paise"] == 3000
    assert completed["payment_status"] == "REFUNDED"

    # Duplicate refund notification is ignored
    dup_refund = apply_order_event(completed, event("e4", "refund_processed", amount_paise=2000))
    assert dup_refund["refunded_paise"] == 3000
    assert dup_refund["processed_event_ids"] == ["e1", "e2", "e3", "e4"]


def test_cancellation_then_payment_confirmed_then_refund():
    order = new_order("O-CNC", 4500)
    cancelled = apply_order_event(order, event("e1", "cancel_requested"))
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["payment_status"] == "UNPAID"
    assert cancelled["refund_due_paise"] == 0

    paid = apply_order_event(cancelled, event("e2", "payment_confirmed"))
    assert paid["status"] == "CANCELLED"
    assert paid["payment_status"] == "PAID"
    assert paid["refund_due_paise"] == 4500

    # Invalid refund amount (> outstanding) is ignored
    over_refund = apply_order_event(paid, event("e3", "refund_processed", amount_paise=5000))
    assert over_refund["refunded_paise"] == 0
    assert over_refund["payment_status"] == "PAID"

    # Full refund
    full = apply_order_event(paid, event("e4", "refund_processed", amount_paise=4500))
    assert full["refunded_paise"] == 4500
    assert full["payment_status"] == "REFUNDED"

def test_dispatch_started_on_rejected_order_is_ignored():
    order = new_order("O-REJ", 1000, "REJECTED")
    out = apply_order_event(order, event("e1", "dispatch_started"))
    assert out["status"] == "REJECTED"
    assert out["processed_event_ids"] == ["e1"]


def test_dispatch_started_on_cancelled_order_is_ignored():
    order = new_order("O-CNC", 1000, "CANCELLED")
    out = apply_order_event(order, event("e1", "dispatch_started"))
    assert out["status"] == "CANCELLED"
    assert out["processed_event_ids"] == ["e1"]

def test_reconciliation_duplicate_order_id_last_write_wins():
    internal = [
        {"order_id": "ORD-DUP", "total_paise": 1000, "status": "PLACED"},
        {"order_id": "ORD-DUP", "total_paise": 2000, "status": "ACCEPTED"},
    ]
    provider = [
        {"order_id": "ORD-DUP", "amount_paise": 2000, "status": "ACCEPTED"}
    ]
    report = reconcile_orders(internal, provider)
    assert report["matched"] == ["ORD-DUP"]
    assert report["amount_mismatches"] == []
    assert report["status_mismatches"] == []
