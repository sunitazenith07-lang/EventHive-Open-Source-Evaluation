# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective

The objective was correctness, not speed. Replayed events were being applied again, which is a correctness bug.

The initial test suite produced 62 failures and 150 passes, and `test_payment_event_replay_idempotent` was one of the tests exposing this problem. No performance benchmark was conducted.

## 2. Options considered

**Option 1: Check the existing `processed_event_ids` list (chosen)**
- Expected benefit: Fixes the bug with one condition and uses the tracking the order already has.
- Risk: Membership checks on a list scan it linearly. This was not measured.
- Decision: Accepted. It is the smallest change and keeps the data structure unchanged.

**Option 2: Change `processed_event_ids` to a set**
- Expected benefit: Faster membership checks for orders with very many events.
- Risk: Changes the data structure, which existing tests and other code may expect to be a list.
- Decision: Rejected. It was not needed to fix the bug and no measurement showed list lookups were a problem.

No alternative implementation was formally benchmarked.

## 3. Changes implemented

- Change: Added duplicate event detection in `apply_order_event()`.
  - Reason: Avoid applying the same event ID more than once.
  - Tests used: `test_payment_event_replay_idempotent`.
  - Measurement method and result: No performance measurement conducted.

## 4. Trade-offs

- A single `if` check is simple and easy to read.
- List lookup is linear in the number of processed events. This is a possible cost for very large event histories, but it was not measured.
- No refactoring was performed.

Correctness and maintainability were prioritised over unnecessary complexity.

## 5. Further improvements

With more time, I would:

1. Benchmark `processed_event_ids` as a list vs a set with a large number of events before changing it.
2. Add tests for events with missing or reused event IDs.

These would be validated with regression tests and, for performance, repeatable measurements against a defined baseline.

If you made no optimization change, state that honestly and compare at least two reasonable options. Correctness and maintainability take priority over unnecessary complexity.