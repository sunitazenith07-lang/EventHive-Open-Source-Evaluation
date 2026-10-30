import pytest

from models import new_order
from service import apply_order_event, reconcile_orders


@pytest.mark.parametrize(
    "event",
    [
        None,
        {},
        {"event_id": "E"},
        {"event_id": "E", "type": "unknown"},
        "bad",
        ["bad"],
    ],
)
def test_malformed_event_payloads_are_ignored(event):
    order = new_order("O1", 1000, "PLACED")
    result = apply_order_event(order, event)
    assert result == order


@pytest.mark.parametrize(
    "internal, provider, expected",
    [
        (
            [None, {"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
            [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
            {"matched": ["A"]},
        ),
        (
            [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
            [None, {"order_id": "A", "amount_paise": 100, "status": "PLACED"}],
            {"matched": ["A"]},
        ),
        (
            [None],
            [{"order_id": "B", "amount_paise": 50, "status": "PLACED"}],
            {"missing_from_internal": ["B"]},
        ),
        (
            [{"order_id": "C", "amount_paise": 10, "status": "PLACED"}],
            [None],
            {"missing_from_provider": ["C"]},
        ),
    ],
)
def test_reconciliation_ignores_malformed_rows(internal, provider, expected):
    report = reconcile_orders(internal, provider)
    for key, value in expected.items():
        assert report[key] == value
