# optimizations.md — Required submission

## 1. Baseline and objective
- **What needed improvement**:
  1. *Correctness & Integrity*: Preventing data corruption from duplicate events, malformed payloads, non-integer amounts, and invalid state transitions.
  2. *Reconciliation Complexity*: Reconciling thousands of internal and external provider transactions efficiently without quadratic $O(N \times M)$ scan latency.
  3. *Determinism*: Ensuring reconciliation reports always produce stably sorted lists regardless of the order in which data enters the system.
  4. *Defensive Immutability*: Ensuring caller-provided dictionaries are never mutated as a side effect during event evaluation.
- **Evidence of room for improvement**:
  The starter already indexed rows in dictionaries and sorted the combined order IDs. The measured defects were correctness gaps in event validation and mismatch classification, not demonstrated quadratic reconciliation work.

## 2. Options considered
- **Option 1: In-Place Mutation vs. Deep Copying**:
  - *Expected Benefit*: In-place mutation avoids memory allocation overhead and is faster in micro-benchmarks.
  - *Risk*: Caller state is silently corrupted if an event is invalid or fails partway through processing. In event streaming architectures, replaying events on mutated state causes subtle non-reproducible bugs.
  - *Decision*: Rejected in-place mutation. Kept defensive copying via `deepcopy` to ensure pure functional transformations where an invalid event returns an uncorrupted duplicate of the original state.
- **Option 2: Linear Scanning vs. Hash Map Indexing for Reconciliation**:
  - *Expected Benefit*: Dictionary indexing avoids repeatedly scanning one list for each record in the other.
  - *Risk*: Requires extra memory proportional to the input size and collapses duplicate IDs.
  - *Decision*: Retained the starter's existing dictionaries; no hash-index optimization was introduced in this change.
- **Option 3: Set Lookups for Valid Event Types**:
  - *Expected Benefit*: Checking `kind in valid_kinds` where `valid_kinds` is a Python `set` provides $O(1)$ lookup time instead of $O(K)$ sequential list scans.
  - *Decision*: Implemented `valid_kinds` as a constant `set`.

## 3. Changes implemented
- **Change 1: Fast-fail event validation guard**:
  - *Reason*: Prevents state mutation for malformed, unknown, or duplicate events. The guard follows the existing defensive copy.
  - *Tests used to protect correctness*: `test_unknown_event_does_not_mutate_order_state`, `test_malformed_event_is_ignored`, `test_payment_event_replay_idempotent`.
- **Change 2: Independent amount/status mismatch classification**:
  - *Reason*: Reports both discrepancies when both fields differ, and marks records matched only when both fields agree. Deterministic dictionary indexing and key sorting were already present in the starter.
  - *Tests used to protect correctness*: `test_reconciliation_results_are_deterministic`, `test_reconciliation_amount_mismatch_matrix`, `test_reconciliation_status_mismatch_matrix`.
  - *Measurement*: No performance benchmark was run. The latest full-suite run completed 221 tests in 0.72 seconds; this is test-run timing, not a performance comparison.
- **Change 3: Type and range-guarded integer arithmetic**:
  - *Reason*: Enforcing `type(amount) is int and amount > 0` prevents Python type coercion vulnerabilities (such as booleans being treated as integer 1 or floats introducing rounding errors).
  - *Tests used to protect correctness*: `test_invalid_refund_amounts_are_ignored`, `test_valid_partial_and_full_refunds`.

- **Change 4: Late payment confirmation refund due**:
  - *Reason*: Allocates the order total when payment confirmation follows cancellation or rejection.
  - *Tests used to protect correctness*: `test_payment_confirmed_after_cancellation_marks_refund_due`, `test_payment_confirmed_after_rejection_marks_refund_due`.

## 4. Trade-offs
- **Simplicity vs. Fine-Grained Structs**:
  Using Python standard dictionaries rather than full `dataclasses` or `pydantic` schemas was maintained to keep dependencies minimal and conform to the project's starter signature contract.
- **Deepcopy Overhead vs. Purity**:
  `deepcopy` creates a new object graph on every event. For extremely high-throughput workloads (e.g., millions of events per second), this could be replaced with structural sharing or frozen dataclasses. However, for reliability, simplicity, and test safety in OrderOps, `deepcopy` provides the best trade-off.

## 5. Further improvements
With additional development time:
1. **Set-Based Deduplication Storage**:
   Convert `processed_event_ids` to a `set` internally (or serialize it as a list on export) to make deduplication checks $O(1)$ instead of $O(E)$ for orders with long event histories.
2. **Streaming Reconciliation for Large Datasets**:
   For reconciliations exceeding memory capacity (e.g., millions of daily transactions), implement an external sort-merge reconciliation stream using file-backed iterators or SQLite.
3. **Structured Event Schema Validation**:
   Introduce typed event models with schema validation to reject malformed event payloads before they reach business service logic.
