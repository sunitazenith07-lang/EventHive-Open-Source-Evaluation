# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 3.13.7
- pytest version: 9.2.0
- Command run: `python -m pytest -q`
- Initial test summary: 62 failed, 150 passed.
- Summary after this fix only: [FILL IN: run `python -m pytest -q` and paste the summary line]

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replay an already processed event using the same event ID. | The event is not applied twice, and its ID appears only once in `processed_event_ids`. | Targeted idempotency run: 20 passed, 180 deselected. | `test_payment_event_replay_idempotent` |
| 2 | [FILL IN: e.g. replay a refund event with the same ID] | [FILL IN] | [RUN AND FILL IN] | [test name or command] |
| 3 | [FILL IN: e.g. replay a status-change event such as rejection] | [FILL IN] | [RUN AND FILL IN] | [test name or command] |
| 4 | [FILL IN: e.g. two different event IDs of the same type] | [FILL IN] | [RUN AND FILL IN] | [test name or command] |
| 5 | [FILL IN: e.g. event with no event ID] | [FILL IN] | [RUN AND FILL IN] | [test name or command] |

## Regression tests added

No new test files or test cases were added. The existing test `test_payment_event_replay_idempotent` was used as the regression check for the duplicate event processing bug.

## Remaining failures or limitations

- Only the duplicate event bug is fixed at this commit. Other tests that cover refund validation, refund eligibility and reconciliation are still expected to fail.
- No test files were modified.
- Behaviour for events with a missing or reused event ID was not tested.  