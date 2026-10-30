# TESTING.md — Required submission

## Test command and environment

- Python version: Python 3.14
- Command run: `python -m pytest -q`
- Actual test summary: `212 passed in 0.26s`
- Demo command: `python -m main`
- Demo result: Successfully printed the reconciliation report with missing orders, amount mismatches, and a status mismatch.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Partial refund of 1 paise | Payment status remains PAID | Passed | `test_valid_partial_and_full_refunds[1]` |
| 2 | Partial refund of 999 paise | Payment status remains PAID until fully refunded | Passed | `test_valid_partial_and_full_refunds[999]` |
| 3 | Full refund of 5000 paise | Payment status changes to REFUNDED | Passed | `test_valid_partial_and_full_refunds[5000]` |
| 4 | Two refunds of 2500 paise each | Total refunded amount becomes 5000 paise | Passed | `test_refunds_cannot_exceed_due[2500-2500]` |
| 5 | Two refunds of 4000 and 2000 paise | Total refunded amount must not exceed 5000 paise | Passed | `test_refunds_cannot_exceed_due[4000-2000]` |

## Regression tests added

No new test cases were added or modified. Existing visible tests were used as regression checks for the refund-processing changes.

The relevant existing tests cover:
- Partial refunds.
- Full refunds.
- Multiple refund events.
- Refund amounts that must not exceed the refund due amount.

## Remaining failures or limitations

- No failures remained in the visible test suite after the fix.
- Final result: 212 passed.
- Hidden tests have not been verified.
- Additional tests for unusual event sequences and duplicate event IDs could improve coverage.