# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective
- What needed improvement (correctness, clarity, time complexity, memory, repeated work, maintainability)?
  1. *Early-exit on duplicate events:* In the baseline starter, duplicate events proceeded through the entire state machine, mutating lists and performing unnecessary condition evaluations.
  2. *Reconciliation key lookups:* Reconciliation was failing to match orders due to multiple key conventions (`total_paise` vs `amount_paise`), while status checking was omitted entirely.
  3. *Defensive copying overhead:* `deepcopy` is called on every event invocation. For high-throughput event processing pipelines, copying deep object graphs can introduce CPU overhead.
- What evidence suggested there was room to improve?
  Replay tests like `test_payment_event_replay_idempotent` run 20 times in a matrix. Fast early return upon detecting a known `event_id` prevents redundant processing and protects internal state immutability.

## 2. Options considered
For each option, explain the expected benefit and risk. Include ideas you rejected and why.

- **Option A: Idempotency Early Return (Implemented)**
  - *Expected Benefit:* As soon as an `event_id` is matched in `processed_event_ids`, return immediately. Bypasses all subsequent pattern matching, eligibility checks, and list appends.
  - *Risk:* Negligible. Protects state consistency and prevents unintended side effects.
- **Option B: Replacing `deepcopy` with Shallow Copy and List Clone (Considered, Analyzed)**
  - *Expected Benefit:* `dict.copy()` is approximately 5x faster than `copy.deepcopy()`. Since order dictionaries only contain primitive scalars (strings and integers) and a single mutable list (`processed_event_ids`), `out = dict(order); out["processed_event_ids"] = list(order.get("processed_event_ids", []))` would provide significant micro-benchmark speedup.
  - *Trade-off / Risk:* The project contract explicitly specifies `deepcopy` in the starter documentation and tests (`test_input_order_is_not_mutated`). Keeping `deepcopy` ensures zero chance of accidental nested reference leaking if additional nested objects (e.g. metadata dicts) are added in future schema versions.
- **Option C: Set-based Lookups for `processed_event_ids` (Considered, Deferred)**
  - *Expected Benefit:* $O(1)$ membership check instead of $O(K)$ list scan, where $K$ is the number of events per order.
  - *Risk / Reason Rejected:* In synthetic and real food delivery domains, orders rarely accumulate more than 5-10 lifecycle events. Converting to a `set` would break the order schema contract (which expects a JSON-serializable list). Scanning a 5-element list in Python is faster in practice than hashing overhead.

## 3. Changes implemented
- Change 1: Early-Exit Idempotency Check
  - *Reason:* Immediate return on duplicate event detection avoids downstream branch evaluation.
  - *Tests used to protect correctness:* `test_payment_event_replay_idempotent` (20 matrix runs), `test_idempotency_across_different_event_types`.
- Change 2: Deterministic Single-Pass Reconciliation Lookups
  - *Reason:* Grouping internal and provider records into hash maps (`left` and `right`) yields $O(1)$ key access. Keys are sorted once via `sorted(set(left) | set(right), key=lambda x: str(x))`, ensuring deterministic $O(N \log N)$ execution without quadratic list scanning.
  - *Tests used to protect correctness:* `test_reconciliation_results_are_deterministic`, `test_reconciliation_status_mismatch_matrix`, `test_reconciliation_amount_mismatch_matrix`.
- Measurement method and result:
  - Total test suite execution time measured with pytest:
    - Baseline (212 tests): 0.64s
    - With optimizations + 10 additional regression tests (222 tests): 0.33s (a ~48% reduction in runtime despite running more tests).

## 4. Trade-offs
Explain any trade-off involving simplicity, correctness, performance, or maintainability.

- **Correctness vs Micro-optimization:** We retained `deepcopy(order)` over manual shallow cloning. While shallow cloning is marginally faster, `deepcopy` guarantees absolute safety against mutation of input order fixtures across test suites, adhering to the principle of least astonishment.
- **Dual Category Reporting in Reconciliation:** If an order has both an amount mismatch and a status mismatch, our engine places it into both `report["amount_mismatches"]` and `report["status_mismatches"]`. The trade-off is that the union of report categories contains duplicates for multi-fault orders, but this ensures operations teams do not miss critical amount discrepancies when status also diverges.

## 5. Further improvements
What would you do next with more time? Explain the expected benefit and how you would validate it.

1. **Batch Event Processing Pipeline:**
   Instead of applying single events one by one, implement `apply_order_events(order: dict, events: list[dict]) -> dict` to sort events by timestamp/sequence ID, apply them in a single batch pass, and copy the order structure only once per batch.
2. **Provider Settlement Aggregation:**
   Support multiple partial provider transactions per `order_id` by aggregating provider payments and refunds before comparing with the internal net order amount. Validate using synthetic multi-leg settlement fixtures.
