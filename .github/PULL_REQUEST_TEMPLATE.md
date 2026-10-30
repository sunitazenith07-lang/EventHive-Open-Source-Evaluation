## What did you change?
- Corrected event idempotency in `apply_order_event` to prevent duplicate event IDs from modifying order state.
- Enforced strict positive integer validation and remaining-due bounds on refunds.
- Handled out-of-order payment confirmation arriving after cancellation/rejection.
- Fixed `reconcile_orders` to resolve schema divergence (`total_paise` vs `amount_paise`) and independently track amount vs status mismatches.
- Implemented `export_awaiting_refund_csv` for stretch work reporting.
- Added 11 regression test cases in `tests/test_regression.py`.

## Root cause
1. Missing idempotency check allowed duplicate event IDs to append and re-process state.
2. Loose type validation allowed booleans (`True`), floats, negative values, and over-refunding.
3. Reconciliation only inspected `amount_paise`, failing on `total_paise` internal records, and ignored status differences.

## Tests
- [x] I ran `python -m pytest -q`.
- [x] I added or updated regression tests for my change.
- [x] I did not delete, skip, weaken or bypass existing tests.
Actual test summary: 226 passed in 0.21s (0 failures, 0 errors, 0 skipped).

## Required problem-solving documents (all three mandatory; 15 marks total)
- [x] `approach.md` completed (5 marks).
- [x] `challenges.md` completed (COMPULSORY; 5 marks).
- [x] `optimizations.md` completed (5 marks).

## Edge cases checked
1. Duplicate event ID replay (`test_payment_event_replay_idempotent`).
2. Boolean refund amounts (`test_invalid_refund_amounts_are_ignored[True]`).
3. Cancellation after dispatch ignored (`test_cancellation_after_dispatch_is_ignored`).
4. Over-refunding beyond due balance rejected (`test_cumulative_refund_exceeding_due_is_rejected`).
5. Dual amount and status mismatch in reconciliation (`test_reconciliation_simultaneous_amount_and_status_mismatch`).

## Design decisions / limitations
Documented in `ORDER_FLOW_NOTES.md`. In-memory functional design guarantees input immutability via `deepcopy`.

## Integrity confirmation
- [x] This is my own individual work.
- [x] I have followed the evaluation's AI-use policy.
- [x] I can explain my changes and make a small live modification if asked.
