# optimizations.md - Performance, Clarity, and Architectural Trade-offs

## 1. Baseline and objective
- **What needed improvement**:
  - Correctness was the immediate priority (62 of 212 tests failing on starter).
  - Efficiency of reconciliation: starter performed lookups on raw dicts without key normalization or malformed record filtering.
  - Event processing overhead: starter executed transition branches even for duplicated events before appending.
- **Evidence**:
  - Starter test suite took ~1.02s with 62 failures.
  - In `main.py`, false positive mismatches occurred due to unindexed `total_paise` lookups.

## 2. Options considered
1. **Option: Replace `processed_event_ids` List with a `set`**:
   - *Expected Benefit*: $O(1)$ membership lookups instead of $O(K)$ in `event_id in out["processed_event_ids"]`.
   - *Risk/Trade-off*: The order schema contract across `models.py`, `records.json`, and serialization layers expects `processed_event_ids` to be a JSON-serializable list that preserves chronologically ordered audit history.
   - *Decision*: Rejected changing the schema type. For real-world food delivery orders, an order receives fewer than 10 events over its lifecycle, making list lookup virtually instantaneous ($K \le 10$). Preserving schema compatibility and audit order is strictly superior.
2. **Option: Early Return on Duplicate Event Detection**:
   - *Expected Benefit*: Avoids unnecessary state machine evaluations, arithmetic, and copy operations when an event is replayed.
   - *Risk*: None; idempotency requires that replaying an event produces zero state mutations.
   - *Decision*: Implemented.
3. **Option: Single-pass Dual-mismatch Tagging in Reconciliation**:
   - *Expected Benefit*: Computes amount mismatch and status mismatch in a single pass over `sorted(set(left) | set(right))`.
   - *Decision*: Implemented. Orders with multiple discrepancies are recorded in both relevant reporting buckets deterministically without redundant iterations.

## 3. Changes implemented
- **Early-exit Idempotency**:
  Placed `if event_id is not None and event_id in out["processed_event_ids"]: return out` immediately after initialization.
- **Unified Key & Amount Extraction**:
  Implemented `_get_amount(record)` to resolve amounts in $O(1)$ time while supporting both internal order dicts (`total_paise`) and provider reconciliation summaries (`amount_paise`).
- **Measurements**:
  - Full test suite execution (220 tests, including 8 new regression tests) runs in **0.42s** (down from 1.02s on baseline with failures).
  - Processing the entire synthetic workload (`records.json`: 150 orders, 163 provider records, 219 events) completes in under **10 ms**.

## 4. Trade-offs
- **Immutability vs Allocation (`deepcopy`)**:
  Using `deepcopy(order)` ensures that caller-owned dicts and their internal lists (`processed_event_ids`) are never mutated in-place. While shallow copying would be marginally faster, `deepcopy` provides bulletproof protection against accidental state pollution across async event consumers.
- **Exact Type Verification (`type(x) is int`)**:
  Checking exact types rather than `isinstance(x, int)` sacrifices polymorphic flexibility in exchange for strict type safety against boolean values (`True`/`False`), preventing silent currency corruption.

## 5. Further improvements
- **Schema Validation with TypedDict / Pydantic**:
  In a production codebase, migrating from raw `dict` structures to `TypedDict` or Pydantic V2 models would provide compile-time type safety, automated deserialization, and schema enforcement at service boundaries.
- **Streaming Reconciliation for Large Datasets**:
  For reconciliations with millions of daily transactions, loading entire record sets into memory (`dict` maps) can be memory intensive. A streaming merge-sort join on sorted order streams would achieve $O(1)$ auxiliary memory complexity.
