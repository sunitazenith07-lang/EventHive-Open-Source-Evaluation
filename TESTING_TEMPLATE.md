# Test notes

## Environment
- Python version: 3.15.1
- Command run: `python -m pytest -q`
- Result: 243 passed in 0.05s

## Edge cases and evidence

| # | Input / scenario | Expected outcome | Actual outcome | Evidence |
|---|---|---|---|---|
| 1 | `apply_order_event(new_order("O1", 1000), None)` | No crash; order remains unchanged | Returned a deep-copied order with no mutation | `test_malformed_events_are_ignored[None]` |
| 2 | `apply_order_event(order, {})` | Empty dict is ignored | State remains stable and no exception is raised | `test_malformed_events_are_ignored[{}]` |
| 3 | `apply_order_event(order, {"event_id": "E", "type": "unknown"})` | Unknown event type is treated as a no-op | Status and payment remain unchanged | `test_malformed_events_are_ignored[unknown]` |
| 4 | `reconcile_orders([None, {"order_id": "A", ...}], [{"order_id": "A", ...}])` | Malformed rows are ignored; valid order is matched | `matched == ["A"]` without a crash | `test_reconcile_skips_malformed_rows` |
| 5 | `reconcile_orders([None], [{"order_id": "B", ...}])` | Provider-only record appears as missing from internal | Report returns `missing_from_internal == ["B"]` | `test_reconcile_skips_malformed_rows` |
| 6 | Duplicate `event_id` for `payment_confirmed` | Replay is ignored | No second mutation or duplicate refund effect | Regression coverage in `tests/test_contract.py` |

## Summary
The repository’s current test suite demonstrates that malformed inputs, duplicate replay, and reconciliation anomalies are handled safely and deterministically without changing the code or weakening the checks.
