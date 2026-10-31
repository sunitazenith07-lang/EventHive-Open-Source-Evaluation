# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 3.13.7
- pytest version: 9.2.0
- Command run: `python -m pytest -q`
- Initial summary: 62 failed, 150 passed.
- After my first 6 new tests: 4 failed, 214 passed (wrong event key in my test helper, not a `service.py` bug).
- Final summary: 226 passed.

## Edge-case evidence
Existing tests were already in the repo; new tests are in `tests/test_my_regressions.py`.

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replay an already processed event ID | Not applied twice | Passed (targeted run: 20 passed) | `test_payment_event_replay_idempotent` (existing); `test_refund_replay_same_event_id_not_applied_twice` (new) |
| 2 | Refund is zero, negative, boolean, non-integer or other invalid type | Ignored; `refunded_paise` unchanged | Passed | `test_invalid_refund_amounts_are_ignored` (existing) |
| 3 | Refund 1 paisa over the remaining balance | Ignored | Passed | `test_refund_one_paisa_over_remaining_is_ignored` (new) |
| 4 | Partial refund, then the exact remainder | `PAID` after partial; `REFUNDED` when due is reached | Passed | `test_refund_exactly_equal_to_remaining_completes_refund` (new) |
| 5 | Refund for an ineligible order state | Not processed | Passed (targeted matrix: 12 passed) | `test_refund_eligibility_matrix` (existing) |
| 6 | Cancel after dispatch | Status stays `OUT_FOR_DELIVERY` | Passed | `test_cancel_after_dispatch_is_ignored` (new) |
| 7 | Same amount, different status | In `status_mismatches`, not `matched` | Passed | `test_reconciliation_status_mismatch_matrix` (existing); `test_reconcile_same_amount_different_status_is_status_mismatch` (new) |
| 8 | Both amount and status differ | Only `amount_mismatches` (current `if`/`elif`) | Passed | `test_reconcile_both_differ_reports_only_amount_mismatch` (new) |

## Regression tests added
`tests/test_my_regressions.py` has 14 new tests; no existing test file was modified.
- Duplicate events: `test_refund_replay_same_event_id_not_applied_twice`.
- Refunds: `test_refund_after_full_refund_is_ignored`, `test_refund_one_paisa_over_remaining_is_ignored`, `test_refund_exactly_equal_to_remaining_completes_refund`.
- Reconciliation: four tests for matched, status-only, amount-only and both-differ, plus `test_reconcile_orders_missing_on_one_side`.
- Other: `test_cancel_after_dispatch_is_ignored`, `test_apply_order_event_does_not_mutate_input`, `test_ord_201_example_sequence`.

## Remaining failures or limitations
- The final suite has no failures.
- Two new tests document current behaviour that may not be the intended rule: `test_events_without_event_id_current_behaviour` and `test_ignored_refund_still_records_event_id_current_behaviour`.
- If both amount and status differ, only the amount mismatch is reported.
- The demo output has an empty `status_mismatches`, so it does not exercise that branch.
- No performance tests were run.