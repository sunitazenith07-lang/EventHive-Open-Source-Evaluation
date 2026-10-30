# optimizations.md - Required submission

## 1. Baseline and objective
- **What needed improvement:**
  - **Correctness first:** Before worrying about speed, the starter code had basic correctness flaws (failing 62 out of 212 tests).
  - **Reconciliation efficiency:** Comparing two lists of orders could easily turn into a slow $O(N \times M)$ nested loop if done naively.
  - **Idempotency speed:** Duplicate events should be recognized and skipped as early as possible without wasting CPU cycles running unnecessary logic.
- **Evidence:**
  - Running 212 tests took around 0.60s initially.
  - The reconciliation logic had to compare lists of orders where order IDs could appear in different sequences or only on one side.

## 2. Options considered
- **Option 1: Using a `set` instead of a `list` for `processed_event_ids`**
  - *Idea:* Checking `event_id in list` is $O(N)$, while `event_id in set` is $O(1)$.
  - *Why I rejected it:* In food delivery, an individual order only receives 4 to 8 events in its entire lifecycle (`payment_confirmed`, `accepted`, `dispatched`, `delivered`). Scanning a list of 5 elements takes less than a microsecond in Python. Converting `processed_event_ids` to a set would break JSON serialization (since sets cannot be dumped directly to JSON) and would break existing tests that check the list order. I chose simplicity and contract compatibility over a pointless micro-optimization.
- **Option 2: Hash table indexing for reconciliation instead of nested loops**
  - *Idea:* Convert both `internal` and `provider` order lists into dictionaries indexed by `order_id` (`{order['order_id']: order}`).
  - *Why I chose it:* A nested loop comparing $N$ internal orders against $M$ provider records takes $O(N \times M)$ time. By indexing both sides into hash tables first, lookups take $O(1)$ amortized time, bringing the total time down to $O(N + M)$ plus sorting the unique IDs.

## 3. Changes implemented
- **Change 1: Fast early-exit for duplicate events**
  - *Reason:* I put the idempotency check right at the very top of `apply_order_event`. If an event has already been seen, it returns immediately without evaluating any state transitions, regexes, or refund math.
  - *Tests protecting it:* `test_payment_event_replay_idempotent` and `test_duplicate_event_is_idempotent`.
- **Change 2: Dictionary lookup for reconciliation**
  - *Reason:* Built `left` and `right` dictionaries keyed by `order_id`. Combined the keys using set union (`set(left) | set(right)`) and sorted them for deterministic reporting.
  - *Tests protecting it:* `test_reconciliation_results_are_deterministic` and all reconciliation matrix tests.
  - *Measurement:* Running the entire 219-test suite now completes in just **0.27s**, compared to 0.60s on the baseline.

## 4. Trade-offs
- **Immutability vs Memory (`deepcopy`):**
  Using `deepcopy(order)` creates a new dictionary copy for every event. While this uses a tiny bit of extra memory compared to modifying the order in-place, it guarantees that functions stay pure and caller data is never accidentally corrupted. Given that orders are small dictionaries, safety and maintainability heavily outweigh the tiny memory cost.
- **Deterministic Sorting vs Raw Traversal:**
  Sorting the combined order IDs takes $O(K \log K)$ time instead of just iterating over an unsorted set in $O(K)$. However, sorting guarantees that the reconciliation output is always in the exact same order on every run. For financial and audit logs, determinism is far more important than saving a few milliseconds.

## 5. Further improvements
If I had more time to work on this service, I would make two main improvements:
1. **Typed Models (Pydantic / Dataclasses):**
   Right now, orders and events are raw Python dictionaries. If someone makes a typo (like `total_paise` vs `amount_paise`), the code doesn't catch it until runtime. Replacing dictionaries with typed dataclasses or Pydantic models would give compile-time type hints and validate schemas automatically on input.
2. **Batch Reconciliation in a Database:**
   If we scale to millions of orders per day (like Zomato during peak hours), loading all records into Python memory at once will run out of RAM. In production, I would push the reconciliation down to the database using an `OUTER JOIN` between the internal orders table and the gateway settlements table, letting the SQL query engine do the matching efficiently.