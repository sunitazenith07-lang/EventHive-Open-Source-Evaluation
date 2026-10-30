# TESTING.md — Required submission

## Test command and environment
- Python version: 3.13.15 (or 3.10+)
- Command run: `python3 -m pytest -q`
- Actual test summary: All tests passed successfully.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | `amount_paise = True` | Ignored (invalid type) | Ignored, refunded paise = 0 | `test_invalid_refund_amounts_are_ignored` |
| 2 | Cancel after dispatch | Status remains `OUT_FOR_DELIVERY` | Status unchanged | `test_order_state_transition_matrix` |
| 3 | Duplicate event ID replay | Processed once, idempotent | State unchanged on second run | `test_payment_event_replay_idempotent` |
| 4 | Refund exceeds due amount | Refund rejected | Refunded paise unchanged | `test_refunds_cannot_exceed_due` |
| 5 | Mismatched order status | Flagged in `status_mismatches` | Listed correctly in report | `test_reconciliation_status_mismatch_matrix` |

## Regression tests added
- Fixed boolean type injection trap for refund amounts.
- Fixed zero-due refund status mutation bug.
- Fixed reconciliation status mismatch tracking.

## Remaining failures or limitations
None. All visible and unit tests pass successfully.

