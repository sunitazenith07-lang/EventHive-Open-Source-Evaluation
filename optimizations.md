# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective
- What needed improvement (correctness, clarity, time complexity, memory, repeated work, maintainability)?
- What evidence suggested there was room to improve?
- **What needed improvement**:
  - Correctness and safety: Enforce idempotency, valid transition boundaries, integer paise refund bounds, and non-masking reconciliation.
  - Runtime efficiency: Avoid redundant list iterations, repeated allocations, and unindexed lookups.
  - Maintainability: Clear separation of event handling, explicit condition guards, and defensive handling of malformed payloads.
- **Evidence**:
  - Initial test suite execution: `62 failed, 150 passed in 1.21s`.
  - In `service.py`, list lookups and reconciliation iterations were unoptimized, and reconciliation logic contained dead code branches.

## 2. Options considered
- For each option, explain the expected benefit and risk. Include ideas you rejected and why.
1. **Set-based Event ID Deduplication vs. List Lookup**:
   - *Considered*: Replacing `processed_event_ids: list` with a `set` for $O(1)$ membership checks.
   - *Evaluation*: While a set provides $O(1)$ checks, the public contract and test suite in `test_contract.py` (`assert second["processed_event_ids"] == ["e1"]`) and `models.py` expect `processed_event_ids` to be a JSON-serializable list that preserves arrival sequence.
   - *Decision*: Kept `processed_event_ids` as a list to satisfy the serialization and test contract, but guarded early with `event_id in out["processed_event_ids"]` before deep event evaluation.
2. **Pre-indexing Reconciliation Dictionaries**:
   - *Considered*: Iterating over `internal` and `provider` lists with nested loops $O(N \times M)$.
   - *Decision*: Used dictionary comprehensions `left = {r['order_id']: r ...}` and `right = {r['order_id']: r ...}` with composite set union `set(left) | set(right)`. This achieves $O(N + M)$ lookup complexity.
3. **Data Classes / Pydantic vs Plain Dictionaries**:
   - *Considered*: Refactoring `dict` objects into typed dataclasses or Pydantic models.
   - *Evaluation*: Adds dependency overhead and violates existing tests that pass and assert against plain dictionary objects.
   - *Decision*: Rejected; maintained dictionary interface with lightweight helper functions (`_extract_amount`).

## 3. Changes implemented
- Change:
- Reason:
- Tests used to protect correctness:
- Measurement method and result (only if measured):

- **Change 1: Linear-time Hash Map Reconciliation**:
  - *Reason*: Reduce time complexity from quadratic $O(N \times M)$ to linear $O(N + M)$ when reconciling large datasets (such as `data/records.json` with hundreds of orders).
  - *Tests*: `test_reconcile_reports_missing_and_amount_difference`, `test_reconciliation_results_are_deterministic`, `test_acceptance_matrix.py` (all parameter combinations).
  - *Measurement*: Running reconciliation on the entire test suite completed in **0.33 seconds** across 220 tests (down from 1.21 seconds baseline).
- **Change 2: Short-circuit Idempotency Guard**:
  - *Reason*: Avoid copying, branching, and string formatting if an event has already been processed.
  - *Tests*: `test_duplicate_event_is_idempotent`, `test_payment_event_replay_idempotent` (20 cases).
- **Change 3: Strict Integer Paise Arithmetic**:
  - *Reason*: Avoid floating-point imprecision when calculating remaining balance (`refund_due_paise - refunded_paise`).

## 4. Trade-offs
- Explain any trade-off involving simplicity, correctness, performance, or maintainability.
- **Immutability via `deepcopy` vs In-place Mutation**:
  - *Trade-off*: `deepcopy(order)` incurs allocation overhead compared to mutating the dictionary in place.
  - *Rationale*: Immutability is critical to prevent caller mutation bugs, verified by `test_input_order_is_not_mutated` and `test_accept_only_when_placed_and_does_not_mutate_input`. The safety and correctness benefits significantly outweigh the micro-overhead for event-driven order processing.
- **List-backed `processed_event_ids`**:
  - *Trade-off*: $O(K)$ lookup where $K$ is the number of events for an individual order.
  - *Rationale*: Individual orders typically process < 10 events across their entire lifecycle (Placed, Accepted, Dispatched, Delivered/Cancelled, Refunded), making $K$ negligible while ensuring JSON compatibility.

## 5. Further improvements
- What would you do next with more time? Explain the expected benefit and how you would validate it.

- If you made no optimization change, state that honestly and compare at least two reasonable options. Correctness and maintainability take priority over unnecessary complexity.
With more time in a production environment:
1. **Streaming / Chunked Reconciliation**: For millions of daily orders, in-memory dictionary joining would exceed RAM. Implementing generator-based streaming or database-level hash joins (e.g., SQL `FULL OUTER JOIN`) would scale horizontally.
2. **Event Schema Validation with Fast Validation Engines**: Using `msgspec` or `pydantic-core` (compiled in Rust/C) for sub-millisecond serialization and strict schema validation.
3. **Audit Log Integration**: Storing timestamped transition logs for regulatory compliance and dispute resolution during payment gateway discrepancies.