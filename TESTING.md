# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 3.13.7
- pytest version: 9.2.0
- Command run: `python -m pytest -q`
- Initial test summary (before any fix): 62 failed, 150 passed.
- Targeted reconciliation status mismatch test after this fix: [FILL IN]
- Final test summary: 212 passed in 3.57 seconds.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Internal and provider records have the same amount but different statuses. | The order is listed under `status_mismatches`, not `matched`. | [RUN AND FILL IN] | `test_reconciliation_status_mismatch_matrix` |
| 2 | Records have the same amount and the same status. | The order is listed under `matched`. | [RUN AND FILL IN] | [test name or command] |
| 3 | Records have different amounts and the same status. | The order is listed under `amount_mismatches`. | [RUN AND FILL IN] | [test name or command] |
| 4 | Records have different amounts and different statuses. | Only `amount_mismatches` is recorded, because of the `if`/`elif` structure. | [RUN AND FILL IN] | [write a short test or script] |
| 5 | Order exists only on one side. | Reported as `missing_from_provider` or `missing_from_internal`. | `python -m main` output listed `ORD-103` under `missing_from_provider` and `ORD-104` under `missing_from_internal`. | `python -m main` demo output |

## Regression tests added

No new test files or test cases were added. `test_reconciliation_status_mismatch_matrix` was used as the regression check for the reconciliation status mismatch bug.

## Remaining failures or limitations

- The final full test suite completed with 212 passed and no reported failures.
- No test files were modified.
- If both amount and status differ for the same order, only the amount mismatch is recorded.
- The demo output has an empty `status_mismatches` list, so it does not exercise the new branch.
- An ignored (invalid or ineligible) refund event still has its event ID appended to `processed_event_ids`; this was read from the code and was not tested.