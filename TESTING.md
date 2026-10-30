# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 3.14.7
- Command run: python -m pytest -q
- Actual test summary: 212 passed, 0 failed

## Edge-case evidence

| # | Case / input          | Expected behaviour                                                 | Actual result | Test name or evidence |
|---|-----------------------|--------------------------------------------------------------------|---------------|-----------------------|
| 1 |Duplicate Event ID     |Event should be ignored; order state remains unchanged.             |passed         |test_contractpy |
| 2 | Cancel after dispatch |Cancellation should be rejected if status is OUT_FOR_DELIVRY.       |Passed         |test_acceptance_matrix.py |
| 3 |Over Refund            |Refund amount > (due -  refunded) should be rejected.               |Passed         |test_contract.py |
| 4 |Negative Refund        |Refund amount $\le 0$ should be rejected.                           |Passed         |test_contract.py |
| 5 |Reconcilitation Status |Record should be "Mismatched" if amount matches but status differs. |Passed         |test_acceptance_matrix.py |

## Regression tests added
The following defects were fixed, and their corresponding tests in the suite now pass:
- Idempotency Fix: Fixed a bug where repeated events were applied multiple times.
- Refund Validation: Fixed a bug where ineligible orders could be refunded.
- Reconciliation Accuracy: Fixed a bug where only amounts were compared, ignoring status mismatches.

## Remaining failures or limitations
 All required behavior tests passed. No known limitations in the core requirements.
