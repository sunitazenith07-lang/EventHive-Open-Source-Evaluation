# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 3.13.7
- pytest version: 9.2.0
- Command run: `python -m pytest -q`
- Initial test summary (before any fix): 62 failed, 150 passed.
- Targeted refund eligibility matrix after this fix: 12 passed.
- Full-suite summary after this fix: [FILL IN: run `python -m pytest -q` and paste the summary line]

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Refund on an order whose payment status is not `PAID` (e.g. `UNPAID`). | Ignored; `refunded_paise` does not change. | [RUN AND FILL IN] | `test_refund_eligibility_matrix` |
| 2 | Refund on a paid order in `PLACED`, `ACCEPTED` or `OUT_FOR_DELIVERY` state. | Ignored; `refunded_paise` does not change. | [RUN AND FILL IN] | `test_refund_eligibility_matrix` |
| 3 | Refund on a paid order in `DELIVERED` state. | Ignored; `refunded_paise` does not change. | [RUN AND FILL IN] | `test_refund_eligibility_matrix` |
| 4 | Refund on an order in `FAILED` state with payment status `PAID`. | Ignored; this was the case that still failed when only the payment status was checked. | [RUN AND FILL IN] | `test_refund_eligibility_matrix` |
| 5 | Refund on a paid order in `REJECTED` or `CANCELLED` state with a valid amount. | Applied; `refunded_paise` increases. | [RUN AND FILL IN] | `test_refund_eligibility_matrix` |

All five rows are covered by the same matrix test, which passed 12 cases in the targeted run.

## Regression tests added

No new test files or test cases were added. `test_refund_eligibility_matrix` was used as the regression check for the refund eligibility bug.

## Remaining failures or limitations

- Reconciliation status mismatch is not fixed at this commit, so related tests may still fail.
- No test files were modified.
- An ignored (invalid or ineligible) refund event still has its event ID appended to `processed_event_ids`; this was read from the code and was not tested.