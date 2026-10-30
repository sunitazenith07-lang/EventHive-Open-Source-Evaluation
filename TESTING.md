# TESTING.md - Execution record

AI assistance was used to write/debug this change. Confirm evaluation rules before submitting; results below are actual local runs.

## Test command and environment
- Python: 3.14.4
- Setup: `python -m pip install -r requirements-dev.txt` succeeded.
- Untouched baseline: `python -m pytest -q` -> 62 failed, 150 passed in 2.91s.
- Final: `python -m pytest -q` -> 219 passed in 1.62s.
- Final demo: `python -m main` completed and reported ORD-102 under `status_mismatches`.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replay same refund event ID | Refund counted once | Passed | `test_duplicate_refund_event_is_idempotent` |
| 2 | Zero, negative, fractional, boolean, missing, or over-due refund amount | No refund state mutation | Passed | `test_invalid_refund_amounts_are_ignored` |
| 3 | Cancellation after dispatch | Remain `OUT_FOR_DELIVERY` | Passed | `test_cancel_after_dispatch_is_ignored` |
| 4 | Amount and status both differ by order ID | Report both mismatches, not matched | Passed | `test_reconcile_reports_amount_and_status_differences_separately` |
| 5 | Event lacks fields or has a non-string type | Order unchanged | Passed | `test_malformed_event_is_ignored` |
| 6 | Paid rejection with 400 then 600 paise refund | Remain PAID after partial, become REFUNDED at 1000 | Passed | `test_paid_rejection_partial_then_full_refund_flow` |

## Regression tests added
Added coverage for duplicate refund replay, malformed events, simultaneous reconciliation mismatches, and a complete rejection/refund lifecycle.

## Remaining failures or limitations
No test failures remain in the final suite. Duplicate summary rows for a single order ID are still collapsed by the reconciliation dictionaries and are not covered.
