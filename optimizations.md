# optimizations.md - Required submission

## 1. Baseline and objective
- **What needed improvement:**
  - **Correctness and early-exit efficiency:** `apply_order_event` unconditionally executed state-transition branches and appended duplicate `event_id`s even when replaying already-processed events.
  - **Maintainability and type safety:** Paise validation was missing or scattered, risking boolean/float coercion or negative balance corruption.
  - **Observability (Stretch Goal):** Operators needed a fast, deterministic way to summarize orders by lifecycle state across batches.
- **What evidence suggested there was room to improve:**
  - 62 baseline test failures in `pytest -q`, plus inspection of `data/records.json` showing duplicate events, malformed records, and 150+ order batches.

## 2. Options considered
- **Option A: Early-exit idempotency check before state evaluation (Implemented)**
  - *Benefit:* Immediately returns on duplicate `event_id` without evaluating transition branches or mutating state.
  - *Risk:* None, provided `order` is deep-copied first so caller immutability (`test_input_order_is_not_mutated`) is preserved.
- **Option B: Convert `processed_event_ids` from `list` to `set` inside the order dictionary (Rejected)**
  - *Benefit:* $O(1)$ lookup instead of $O(k)$ list membership per order.
  - *Why rejected:* Contract tests (`test_duplicate_event_is_idempotent` and `test_payment_event_replay_idempotent`) explicitly assert ` result["processed_event_ids"] == [event_id]` (a JSON-serializable `list`). Since each single order typically processes fewer than 10 lifecycle events, a `list` preserves full contract and JSON compatibility with negligible overhead.
- **Option C: Avoid `deepcopy` on no-op events by shallow-copying top-level keys (Rejected)**
  - *Benefit:* Slightly lower memory allocation per call.
  - *Why rejected:* `processed_event_ids` is a nested mutable list; `deepcopy` guarantees zero accidental mutation of the caller's input dictionary across all edge cases.
- **Option D: Add deterministic `summarize_orders_by_state` helper (Implemented — Optional Stretch Item)**
  - *Benefit:* Single-pass $O(N)$ aggregation + sorted key output for operational reporting.

## 3. Changes implemented
- **Change 1:** Centralized strict integer validation in `_is_strict_int(val)` and added early-exit idempotency in `apply_order_event`.
- **Change 2:** Added `_clean_records` and single-pass dictionary indexing in `reconcile_orders` with deterministic sorting over the union of valid `order_id`s.
- **Change 3:** Implemented the optional stretch function `summarize_orders_by_state(orders)` in `service.py`.
- **Tests used to protect correctness:** All 212 starter tests plus 8 new regression and stretch tests in `tests/test_contract.py` (`220 passed in 0.18s`).

## 4. Trade-offs
- Prioritized **immutability, contract compliance, and defensive input sanitization** over micro-optimizing `deepcopy`. The entire 220-test suite (including replaying all 219 events and reconciling 150 internal vs 163 provider records from `data/records.json`) executes in `0.18s`.

## 5. Further improvements
- If an order could accumulate thousands of events in a long-lived stream, we could maintain an internal `_seen_event_ids` set alongside the serialized list or persist `event_id`s in an indexed idempotency table with a TTL.
