# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
- Commands run before editing: `python -m pytest -q`
- Initial test result: 62 failed, 150 passed (212 tests total).
- Demo/output observed: [FILL IN: output of `python -m main` before this fix, or write "not recorded before this fix"]

## 2. Codebase understanding
- Important files and functions inspected:
  - `service.py`: `apply_order_event()`.
  - `models.py`: `new_order()`, which creates an order with an empty `processed_event_ids` list.
  - Relevant tests in `tests/test_acceptance_matrix.py`.
- Order lifecycle or data flow traced:
  - Events are passed to `apply_order_event()`, which returns an updated copy of the order.
  - Each order keeps a `processed_event_ids` list that records which events have already been applied.
- How understanding was confirmed:
  - Inspected `apply_order_event()` and the `processed_event_ids` field.
  - Ran the replay tests and checked the result after the change.

## 3. Investigation and implementation strategy

- Issue 1: Duplicate event processing.
  - Symptom: Replaying an event with the same event ID could apply it more than once.
  - Investigation: Examined `processed_event_ids` and the `test_payment_event_replay_idempotent` test.
  - Fix: Return the unchanged order copy if the event ID is already in `processed_event_ids`:
    ```python
    if event_id in out["processed_event_ids"]:
        return out
    ```
  - Evidence: The targeted idempotency test run passed 20 cases (20 passed, 180 deselected).

## 4. Implementation decisions
- Main changes and why:
  - One check in `apply_order_event()` so a repeated event ID makes no changes to the order.
- Alternatives considered and why rejected:
  - Changing `processed_event_ids` from a list to a set was not chosen: it changes the data structure and was not needed to fix the bug.
  - No alternative implementation was formally benchmarked.
- Assumptions:
  - An event ID identifies one event that should only be processed once.

## 5. Verification
- Tests added or changed: No test files were modified. Existing tests were used as regression checks.
- Commands run and actual results:
  - Initial `python -m pytest -q`: 62 failed, 150 passed.
  - Targeted idempotency run: 20 passed, 180 deselected.
  - Full `python -m pytest -q` after this fix only: [FILL IN: run it and paste the summary line]
- Edge cases verified:
  - Replaying an already processed event ID.
- Remaining failures or known limitations:
  - Other failing tests remain at this commit; they belong to the refund and reconciliation bugs fixed in later commits.
  - Behaviour for events with a missing event ID was not investigated.

Record actual engineering decisions and evidence. Do not claim tests or experiments you did not run.