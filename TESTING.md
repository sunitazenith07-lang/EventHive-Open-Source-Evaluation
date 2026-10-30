# TESTING.md — Required submission

## Test command and environment
- Python version: Python 3.15.1
- Command run: `pytest -q`
- Actual test summary: 233 passed in 0.06s

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | `apply_order_event(new_order("O1", 1000), None)` | No crash; order remains unchanged | Returned the original order unchanged | `test_malformed_events_are_ignored[None]` |
| 2 | `apply_order_event(order, {})` | Ignore empty event dict and keep state stable | Returned a deep-copied order without mutation | `test_malformed_events_are_ignored[{}]` |
| 3 | `apply_order_event(order, {"event_id": "E", "type": "unknown"})` | Unknown event types are no-ops | Status and payment remained unchanged; no exception thrown | `test_malformed_events_are_ignored[unknown]` |
| 4 | `reconcile_orders([None, {"order_id": "A", "amount_paise": 100, "status": "PLACED"}], [{"order_id": "A", "amount_paise": 100, "status": "PLACED"}])` | Ignore malformed rows and match valid order `A` | Report contained `matched == ["A"]` and did not crash | `test_reconcile_skips_malformed_rows` |
| 5 | `reconcile_orders([None], [{"order_id": "B", "amount_paise": 50, "status": "PLACED"}])` | Provider-only record is reported as `missing_from_internal` | Report was `{"missing_from_internal": ["B"]}` | `test_reconcile_skips_malformed_rows` |
| 6 | `apply_order_event(order, ["bad"])` or `"bad"` | Non-dict events should be ignored | No exception; original order preserved | `test_malformed_events_are_ignored[bad]` and `test_malformed_events_are_ignored[event5]` |

## Regression tests added
- Fixed the crash path where the service accessed `.get()` on `None`, strings, and list payloads rather than validating the event shape first.
- Added regression coverage for malformed event payloads in both `tests/test_contract.py` and `tests/test_acceptance_matrix.py`.
- Added reconciliation regressions to ensure `None` rows and missing order IDs are skipped without corrupting the comparison report.

## Remaining failures or limitations
- No remaining failures in the repository test suite after the fix.
- The service still intentionally treats malformed or unknown events as safe no-ops, which matches the stated contract to avoid mutating order state when input is invalid.
