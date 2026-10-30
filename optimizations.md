# optimizations.md - Required submission

## 1. Baseline and objective
- **What needed improvement:**
  - *Correctness:* 62 failing tests across event replay idempotency, invalid refund type checking, refund boundary safety, and status reconciliation.
  - *Reconciliation Efficiency:* The starter code had potential O(N^2) lookups if non-indexed structures were used, and inefficient multiple iterations.
  - *Data Normalization:* The starter reconciliation crashed or miscategorized records when internal orders used `total_paise` while provider records used `amount_paise`.
  - *Defensive Resilience:* Missing fields or malformed inputs had the potential to raise `KeyError` or `AttributeError`.
- **Evidence:**
  - Baseline execution completed 212 tests in ~0.98s with 62 failures.
  - Offline demo reported false-positive amount mismatches on `sample_orders()` due to key differences (`total_paise` vs `amount_paise`).

## 2. Options considered
- **Option 1: Using sets for idempotency tracking**
  - *Expected benefit:* O(1) lookup time for checking whether an `event_id` was already processed.
  - *Risk / Reason Rejected:* The contract requires `processed_event_ids` to remain a JSON-serializable list and maintain the ordered sequence of events received. Converting `processed_event_ids` to a set would break serialization and test assertions expecting a list (`assert twice["processed_event_ids"] == [event_id]`). Instead, we retained a list and guarded checks cleanly.
- **Option 2: Single-pass dictionary hash lookups for reconciliation**
  - *Expected benefit:* Indexed dictionary lookup by `order_id` achieves O(N + M) time complexity instead of O(N * M) nested looping, where N is the number of internal orders and M is the number of provider records.
  - *Decision:* Implemented. Filtered and keyed valid records into dictionaries `left` and `right`, followed by iterating over the union of unique order keys.
- **Option 3: Strict non-boolean type guards (`isinstance(amount, int) and not isinstance(amount, bool)`)**
  - *Expected benefit:* Zero overhead branch checking that prevents subtle type coercion bugs in Python financial calculations without needing external schema libraries or heavy decimal modules.
  - *Decision:* Implemented.
- **Option 4: In-place order mutation vs deepcopy**
  - *Expected benefit:* Avoid deepcopy memory allocation.
  - *Risk / Reason Rejected:* In-place mutation breaks non-destructive testing requirements (`test_accept_only_when_placed_and_does_not_mutate_input`). Contract compliance requires returning a new modified copy.

## 3. Changes implemented
- **Change 1: Hash-mapped reconciliation indexing**
  - *Reason:* By building `left` and `right` dictionary maps on `order_id`, matching occurs in O(N + M) time.
  - *Tests used to protect correctness:* `test_reconciliation_status_mismatch_matrix`, `test_reconciliation_amount_mismatch_matrix`, `test_reconciliation_results_are_deterministic`.
  - *Measurement method and result:* 212 tests completed in 0.45s (improved from 0.98s baseline on the same environment).
- **Change 2: Key-agnostic amount extractor**
  - *Reason:* Internal orders track `total_paise` whereas provider transactions record `amount_paise`. Reading `a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")` prevents false discrepancies.
  - *Tests used to protect correctness:* Offline demo (`python -m main`), `test_regression_simultaneous_amount_and_status_mismatch`.
- **Change 3: Early-exit idempotency check**
  - *Reason:* Returning early before cloning large nested structures or evaluating state branches prevents wasted CPU cycles when duplicate events are replayed.
  - *Tests used to protect correctness:* `test_payment_event_replay_idempotent`, `test_replay_with_conflicting_payload_is_ignored`.

## 4. Trade-offs
- **Immutability vs Memory Allocation:** Using `deepcopy(order)` creates a full copy of the order dictionary for every event. In memory-constrained environments with high event throughput, a shallow copy or copy-on-write proxy could save allocations; however, `deepcopy` ensures complete isolation of nested lists such as `processed_event_ids`, guaranteeing zero unintended caller side effects.
- **List vs Set for `processed_event_ids`:** Retaining a list preserves event arrival ordering and straightforward JSON serialization at the cost of O(K) lookup time where K is the number of events per order. Because individual orders in food delivery typically have fewer than 10 events, K is negligible in practice and list lookup overhead is microscopic.

## 5. Further improvements
- **Stream-based batch reconciliation:** For multi-million row datasets, loading all records into memory simultaneously can exhaust RAM. A chunked generator or external merge-sort on sorted order IDs would scale to arbitrary record sizes with constant memory overhead.
- **Idempotency with sliding TTL cache:** In production, storing event IDs in a distributed Redis cache with a 72-hour TTL would enforce idempotency across multi-node workers while preventing order records from accumulating stale event IDs.
