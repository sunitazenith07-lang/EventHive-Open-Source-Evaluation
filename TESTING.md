# TESTING.md — Test Evidence and Edge Cases

## Test command and environment
- Python version: Python 3.13.x
- Command run: `python -m pytest -q`
- Actual test summary: 212 passed, 0 failed in 0.64s

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Duplicate event replay (`event_id` already processed) | Event should be ignored, state remains unchanged, and `processed_event_ids` does not duplicate the ID. | Event ignored, state unchanged, list remains `['e1']`. | `test_duplicate_event_is_idempotent` |
| 2 | Refund with non-integer type (`None`, strings, floats, lists, dicts) | Invalid refund amounts must be ignored without raising exceptions or altering `refunded_paise`. | Refund ignored (`refunded_paise == 0`). | `test_invalid_refund_amounts_are_ignored` |
| 3 | Refund with boolean value (`True` or `False`) | Booleans subclass `int` in Python but must be rejected as invalid refund amounts. | Boolean refunds ignored (`refunded_paise == 0`). | `test_invalid_refund_amounts_are_ignored` |
| 4 | Cumulative refunds exceeding amount due (`refund_due_paise`) | Total refunded amount cannot exceed the outstanding due amount. Excess partial refund is ignored/capped. | Refunded amount capped securely at `refund_due_paise`. | `test_refunds_cannot_exceed_due` |
| 5 | Reconciliation with status mismatches between internal and provider | Orders with differing statuses must be correctly categorized under `status_mismatches`. | Order ID correctly reported in `status_mismatches`. | `test_reconcile_reports_status_difference` |

## Regression tests added
- **Idempotency Guard:** Added early return checks to prevent duplicate event application and list bloat upon replaying events.
- **Strict Type Validation:** Enforced `type(amount) is int and not isinstance(amount, bool)` to filter out non-integer inputs and boolean edge cases.
- **Boundary Capping:** Added cumulative validation on `refunded_paise` to strictly respect `refund_due_paise` limits.

## Remaining failures or limitations
- None. All 212 tests passed successfully.