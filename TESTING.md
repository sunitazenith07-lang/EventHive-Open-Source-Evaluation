# TESTING.md — Required submission

## Test command and environment
- Python version: Python 3.14.7
- Command run: `python -m pytest -q`
- Actual test summary: `215 passed, 1 warning in 0.29s`

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Duplicate `payment_confirmed` with same `event_id` | Second event ignored; `processed_event_ids` has 1 item | Passed; state unchanged on replay | `test_duplicate_event_is_idempotent` & `test_payment_event_replay_idempotent` |
| 2 | Cancellation requested after dispatch (`OUT_FOR_DELIVERY`) | Status remains `OUT_FOR_DELIVERY`; cancellation ignored | Passed; status preserved | `test_cancel_after_dispatch_is_ignored` |
| 3 | Refund amount passed as boolean `True` | Refund rejected; `refunded_paise` remains 0 | Passed; `refunded_paise == 0` | `test_regression_boolean_refund_is_rejected` |
| 4 | Refund amount exceeding remaining refundable due | Refund rejected; `refunded_paise` unchanged | Passed; `refunded_paise == 0` | `test_refund_cannot_exceed_amount_due` |
| 5 | Order with both amount mismatch and status mismatch | Order ID reported in both mismatch lists | Passed; present in both lists | `test_regression_dual_mismatch` |

## Regression tests added
1. `test_regression_boolean_refund_is_rejected`: Validates that boolean values (`True`/`False`) cannot be coerced to integers in refund processing.
2. `test_regression_total_paise_reconciliation`: Verifies internal orders with `total_paise` reconcile properly against provider records with `amount_paise`.
3. `test_regression_dual_mismatch`: Verifies that an order with both amount and status differences is reported in both categories without being marked as matched.

## Remaining failures or limitations
- 0 failing tests. All 215 visible and regression tests pass.
