# optimizations.md - Required submission

## 1. Baseline and objective
- **What needed improvement:**
  - *Correctness and safety:* The baseline implementation lacked idempotency guards, allowed invalid refund amounts, failed to validate refund eligibility, and omitted status mismatch detection in reconciliation.
  - *Data normalization & lookup efficiency:* Reconciliation compared records using list lookups and assumed hardcoded key names (`amount_paise`), failing to handle internal records initialized with `total_paise`.
  - *Input safety:* Avoiding accidental mutations of input dictionaries during event transitions.
- **What evidence suggested room to improve:**
  - Initial tests failed with `62 failed, 150 passed in 0.84s`.
  - In `main.py`, orders with matching amounts failed to match due to schema key discrepancy.

## 2. Options considered
1. **Idempotency storage (List vs Set):**
   - *Option A (List):* Maintain `processed_event_ids` as a list of strings (`["EV-001", "EV-002"]`).
     - *Pros:* Keeps JSON serialization straightforward and preserves historical event arrival sequence.
     - *Cons:* Lookup `event_id in list` is O(N) where N is the number of processed events per order.
     - *Choice:* Selected Option A because in practical food delivery workflows, an individual order processes fewer than 10 events (payment, accept, dispatch, deliver, refund), making the overhead negligible while ensuring schema compatibility with tests expecting a list.
2. **Event Schema Validation (Pydantic / Dataclasses vs Lightweight Dict Guarding):**
   - *Option A (External schema validation):* Introduce Pydantic models for incoming events.
     - *Pros:* Automatic type coercion and validation errors.
     - *Cons:* Adds third-party dependencies, extra overhead, and breaks zero-dependency dev environment.
     - *Choice:* Selected lightweight inline guards (`type(amount) is int and amount > 0`), which execute in nanoseconds without third-party dependencies.
3. **Reconciliation Mapping (Set Union vs Linear Search):**
   - *Option A:* Build hash maps (`left` and `right`) keyed by `order_id` and compute `set(left) | set(right)` once.
     - *Pros:* O(N + M) time complexity with deterministic sorted iteration.
     - *Choice:* Implemented. Dramatically faster than nested linear searching across records.

## 3. Changes implemented
- **Change 1: Fast Dictionary Lookup & Set-Union Reconciliation**
  - *Reason:* Reconciling internal and provider orders requires matching records by `order_id`. Building dict indexes allows O(1) lookups per order.
  - *Tests used to protect correctness:* `test_reconciliation_results_are_deterministic`, `test_internal_only_order_is_reported`, `test_provider_only_order_is_reported`.
  - *Measurement:* Running reconciliation over the synthetic dataset executes in under 2ms.
- **Change 2: Strict Pure Function Transitions with Defensive Copying**
  - *Reason:* Preserves input immutability so callers and upstream event streams do not experience unexpected side effects.
  - *Tests used to protect correctness:* `test_input_order_is_not_mutated`.

## 4. Trade-offs
- **Immutability vs Allocation:** Using `deepcopy(order)` incurs memory allocation overhead on each event application. In high-throughput streaming systems, persistent data structures or shallow copies of modified fields would be faster. However, for correctness and simplicity in this service, `deepcopy` guarantees zero shared state.
- **Event ID History:** Retaining `processed_event_ids` as a `list` rather than a `set` preserves insertion order for debugging and audit logs at the cost of O(K) lookup time where K is typically <= 10.

## 5. Further improvements
With additional development time, the following enhancements would be explored:
1. **Event Timestamp Ordering & Clock Jitter Handling:** Track event generation timestamps alongside arrival order to detect and queue out-of-order deliveries.
2. **Batch Reconciliation Streaming:** For datasets with millions of records, replace in-memory dictionary joining with an external merge-sort or chunked generator pipeline to maintain constant memory footprint.
3. **Audit Trail Logging:** Store event replay attempts and rejected refund reasons in an audit log for forensic financial tracking.
