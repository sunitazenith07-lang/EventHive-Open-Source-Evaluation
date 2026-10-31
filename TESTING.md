# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 3.13.7
- pytest version: 9.2.0
- Command run: `python -m pytest -q`
- Initial summary (before any fix): 62 failed, 150 passed.
- Targeted reconciliation status mismatch test after this fix: [FILL IN]
- Final summary: 212 passed in 3.57 seconds.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Same amount on both sides, different statuses. | Listed under `status_mismatches`, not `matched`. | [RUN AND FILL IN] | `test_reconciliation_status_mismatch_matrix` |
| 2 | Same amount and same status on both sides. | Listed under `matched`. | [RUN AND FILL IN] | [test name or command] |
| 3 | Different amounts, same status. | Listed under `amount_mismatches`. | [RUN AND FILL IN] | [test name or command] |
| 4 | Different amounts and different statuses. | Only `amount_mismatches` is recorded, because of the `if`/`elif` structure. | [RUN AND FILL IN] | [write a short test or script] |
| 5 | Order present on only one side. | Reported as `missing_from_provider` or `missing_from_internal`. | `python -m main` listed `ORD-103` under `missing_from_provider` and `ORD-104` under `missing_from_internal`. | `python -m main` demo output |

## Regression tests added

No new test files or test cases were added. `test_reconciliation_status_mismatch_matrix` served as the regression check for the reconciliation status mismatch bug.

## Remaining failures or limitations

- The final full suite finished with 212 passed and no reported failures.
- No test files were modified.
- When both amount and status differ for one order, only the amount mismatch is recorded.
- The demo output has an empty `status_mismatches` list, so it does not exercise the new branch.
- An ignored (invalid or ineligible) refund event still has its event ID appended to `processed_event_ids`. I read this from the code and did not test it.