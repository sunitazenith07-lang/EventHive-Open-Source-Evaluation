# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour

The challenge was understanding why replaying an event changed the order a second time, even though each order already stored a `processed_event_ids` list. The list was being tracked, but `apply_order_event()` did not check it before applying an event.

## 2. Evidence

The initial test suite produced:

```text
62 failed, 150 passed
```

The test that exposed this problem:

- `test_payment_event_replay_idempotent`

[FILL IN: paste the assertion error or failing output you saw for this test before the fix, if you have it.]

## 3. What I tried

1. Ran `python -m pytest -q` to get the baseline.
2. Used `pytest -x -vv` to look at failures and their assertions.
3. Examined `apply_order_event()` and found that event IDs were recorded but never checked before processing.
4. Added the check for an already processed event ID and ran the targeted idempotency tests.

## 4. Resolution

- Root cause: `apply_order_event()` did not check whether the event ID was already in `processed_event_ids`.
- What changed: added this check in `service.py`:
  ```python
  if event_id in out["processed_event_ids"]:
      return out
  ```
- Why it addresses the cause: a repeated event ID now returns the unchanged order copy, so the event's effects are not applied twice.

## 5. Proof and regression prevention

- Targeted idempotency run: 20 passed, 180 deselected.
- Full suite after this fix only: [FILL IN]
- No test files were modified.

Related cases that could still break:
- Events with a missing event ID.
- Two different events that reuse the same event ID.

## 6. Unresolved challenge or next step

The other three bugs (refund validation, refund eligibility, reconciliation status mismatch) are not fixed at this commit and are handled in later commits. Behaviour for missing or reused event IDs was not investigated and would need its own focused test.