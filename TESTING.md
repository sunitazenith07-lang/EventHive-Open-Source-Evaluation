# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 3.13.7
- pytest version: 9.2.0
- Command run: `python -m pytest -q`
- Initial test summary (before any fix): 62 failed, 150 passed.
- Summary after this fix: [FILL IN: run `python -m pytest -q` and paste the summary line]

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Refund amount is zero or negative. | Ignored; `refunded_paise` does not change. | [RUN AND FILL IN] | `test_invalid_refund_amounts_are_ignored` |
| 2 | Refund amount is a boolean (`True`/`False`). | Ignored, even though `bool` is a subclass of `int`. | [RUN AND FILL IN] | `test_invalid_refund_amounts_are_ignored` |
| 3 | Refund amount is a string, list, dictionary or decimal. | Ignored; `refunded_paise` does not change. | [RUN AND FILL IN] | `test_invalid_refund_amounts_are_ignored` |
| 4 | Refund amount is greater than the remaining refund due. | Ignored; total refunded never exceeds the refund due. | [RUN AND FILL IN] | `test_refunds_cannot_exceed_due` |
| 5 | Partial refund followed by the remaining amount. | Partial refund does not change payment status to `REFUNDED`; completing the due amount does. | [RUN AND FILL IN] | `test_valid_partial_and_full_refunds` |

## Regression tests added

No new test files or test cases were added. These existing tests were used as regression checks for the refund validation bug:

- `test_invalid_refund_amounts_are_ignored`
- `test_valid_partial_and_full_refunds`
- `test_refunds_cannot_exceed_due`

## Remaining failures or limitations

- Refund eligibility (payment status and order status) and reconciliation status mismatch are not fixed at this commit, so related tests may still fail.
- No test files were modified.
- An ignored invalid refund event still has its event ID appended to `processed_event_ids`; this was read from the code and was not tested.