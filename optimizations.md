# optimizations.md - Required submission

## 1. Baseline and objective
- What needed improvement:
  - Correctness and idempotency in event handling.
  - Elimination of unnecessary re-computations upon duplicate event arrival.
  - Deterministic and linear-time reconciliation between internal and provider datasets.
  - Defensive handling for missing fields and empty collections without extra runtime overhead.
- What evidence suggested room to improve:
  - The baseline test suite took 0.53s with 62 test failures. Duplicate events were re-processing state updates, re-appending to lists, and causing state inconsistency.

## 2. Options considered
- Option A: Refactoring Order and Events into OOP Classes / Data Models
  - Benefit: Static typing and automatic validation schemas.
  - Risk / Trade-off: Violates project rules not to change the project structure or existing function contracts. Overhead of object instantiation on large batch streams.
  - Decision: Rejected. Kept simple standard Python dictionaries.
- Option B: Using an In-Memory Database / SQLite for Reconciliation
  - Benefit: SQL query-based outer joins for missing and mismatched records.
  - Risk / Trade-off: High setup overhead, slow serialization, and unnecessary complexity for moderate list sizes.
  - Decision: Rejected.
- Option C: Set-based Order Indexing and Early-Return Idempotency Guard
  - Benefit: O(1) membership check for duplicate events. O(N + M) dictionary lookups with O(K log K) deterministic sorted output. Zero external dependencies.
  - Decision: Implemented.

## 3. Changes implemented
- Change 1: Early Idempotency Check in `apply_order_event`
  - Reason: Duplicate events immediately return the existing order object rather than executing state transition logic and copying data unnecessarily.
  - Protection: `test_payment_event_replay_idempotent` across 20 event ID variations.
- Change 2: Fast Dictionary Indexing and Key Unification in `reconcile_orders`
  - Reason: `left` and `right` dictionary lookups reduce complexity from O(N * M) nested scanning down to O(N + M) dictionary comprehension, with unified handling of `total_paise` and `amount_paise`.
  - Protection: `test_reconciliation_amount_mismatch_matrix`, `test_internal_only_order_is_reported`, `test_provider_only_order_is_reported`.
- Measurement:
  - Total test run time decreased from **0.53s** on the baseline down to **0.14s - 0.15s** with all 212 tests passing.

## 4. Trade-offs
- Deep Copying vs In-Place Mutation:
  - Using `deepcopy` ensures strict immutability of input orders, avoiding unexpected side-effects across callers. While shallow copying or in-place mutation would be slightly faster, `deepcopy` guarantees safety and correctness across nested lists (e.g. `processed_event_ids`).
- Simplicity vs Overengineering:
  - Selected direct dictionary operations and basic `if/elif` branches rather than external state machine libraries or dynamic dispatch tables, preserving readability for beginner maintainers.

## 5. Further improvements
- With more time and larger datasets:
  1. Memory Optimization: Replace `copy.deepcopy` with persistent immutable data structures or shallow copy where inner lists are copied explicitly (`"processed_event_ids": list(out["processed_event_ids"])`), reducing allocation overhead.
  2. Streaming Reconciliation: Implement generator-based chunking for reconciling millions of records from disk/streams without loading the entire dataset into memory simultaneously.
