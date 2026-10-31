# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective
- What needed improvement:
  - Replayed events were running through all the transition checks instead of returning early.
  - Test run took 2.61s initially.
  - Ensuring the input dictionary isn't mutated without making unnecessary copies.
- What evidence suggested there was room to improve:
  - Duplicate events were doing full processing and appending repeated IDs.

## 2. Options considered
- Early return for duplicate events: Check `event_id in out["processed_event_ids"]` at the start of `apply_order_event` and return immediately. Implemented.
- Using `type(x) is int` instead of `isinstance`: Direct check that avoids boolean values and is slightly faster. Implemented.
- Using a set for `processed_event_ids`: Considered for faster lookups, but rejected because the tests verify list order, and orders only have a few events anyway.
- In-place mutation: Considered removing `deepcopy`, but rejected because tests require the original input to stay unchanged.

## 3. Changes implemented
- Added early return in `apply_order_event`:
  ```python
  if event_id is not None and event_id in out["processed_event_ids"]:
      return out
  ```
- Combined refund validation into one check: `type(amount) is int and amount > 0 and amount <= remaining_due`.
- Built lookup dicts once in `reconcile_orders` and looped over sorted keys.
- Measured result:
  - Baseline: 2.61s for 212 tests.
  - After changes: 0.59s for 221 tests.

## 4. Trade-offs
- `deepcopy` has a small memory cost, but it guarantees callers don't have their data mutated.
- Storing event IDs in a list instead of a set keeps the event order preserved for tests and debugging.

## 5. Further improvements
- For large scale, processing events through a message queue (like Kafka) and storing state in a database with transactions rather than in-memory dicts.