# optimizations.md - Required submission

## 1. Baseline and objective
- What needed improvement:
  1. Idempotency performance: Avoid re-running state machine logic and object mutation when replaying previously seen events.
  2. Reconciliation lookup efficiency: Ensure comparing internal and provider records scales cleanly with $O(N \log N)$ complexity rather than $O(N^2)$.
  3. Correctness and type safety: Prevent unwanted type coercions (such as boolean-to-integer conversion).
- Evidence: 62 test failures and flawed demo reconciliation output.

## 2. Options considered
- Option A (Idempotency Short-Circuit): Return `out` immediately when `event_id in out["processed_event_ids"]`.
  - *Benefit:* Skips all string comparisons, dictionary updates, and refund math on duplicates.
  - *Risk:* None; strictly preserves idempotency semantics. (Implemented)
- Option B (In-Place Mutation vs `deepcopy`): Mutating the input dictionary directly to save memory allocation overhead.
  - *Benefit:* Reduces memory allocation.
  - *Risk:* Violates the strict contract that input order dictionaries must not be mutated (`test_accept_only_when_placed_and_does_not_mutate_input`). (Rejected)
- Option C (Dictionary Hashing for Reconciliation): Indexing both internal and provider record lists into dictionaries keyed by `order_id`.
  - *Benefit:* Allows $O(1)$ lookups per order ID and $O(N \log N)$ total reconciliation time due to deterministic key sorting. (Implemented)

## 3. Changes implemented
- Change 1: Early return on duplicate `event_id` in `apply_order_event`.
  - *Reason:* Guarantees idempotency and saves processing time on repeated event deliveries.
  - *Tests:* `test_payment_event_replay_idempotent` (20 cases), `test_duplicate_event_is_idempotent`.
- Change 2: Key-based dictionary lookup in `reconcile_orders`.
  - *Reason:* Replaced linear search with constant-time hash map lookups.
  - *Tests:* `test_reconciliation_results_are_deterministic` (10 cases).
- Measurement: Full test suite execution takes ~0.29s for 215 tests.

## 4. Trade-offs
- Immutability vs Performance: Using `deepcopy(order)` incurs a small memory copy cost per event, but guarantees pure functional behavior and prevents accidental side effects across concurrent consumers.
- Explicit type filtering: Adding `not isinstance(amount, bool)` introduces a micro-check but prevents subtle financial discrepancies from boolean inputs.

## 5. Further improvements
- Convert `processed_event_ids` to a `set` (or maintain a parallel set) if an order accumulates hundreds of events, reducing lookup time from $O(M)$ to $O(1)$.
