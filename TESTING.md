# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 3.14
- Command run: 'python -m pytest -q'
- Actual test summary: 222 passed.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result |
|---|---|---|---|---|
| 1 | Missing event ID | Ignore event | Passed |
| 2 | Unknown event type | Ignore event | Passed |
| 3 | Duplicate event ID | Ignore duplicate | Passed |
| 4 | Negative Refund | Reject refund | Passed |
| 5 | Excess cumulative refund | Reject excess | Passed |
| 6 | FUll refund | Mark REFUNDED | Passed |

## Regression tests added
Added 6 test cases in  'tests.test_contract_py'.

## Remaining failures or limitations
Duplicate or IDs and malformed reconciliation records need additoinal handling.
