# optimizations.md - Required submission

## 1. Baseline and objective
- **What needed improvement:**
  - *Early exit for duplicate events:* The starter code did not check if an event was already processed, meaning duplicate events ran through all the `if/elif` branches and mutated state a second time. Adding an early idempotency check lets us short-circuit immediately.
  - *Lookup speed in reconciliation:* Comparing internal and provider lists needs to be fast ($O(N + M)$) rather than using nested loops ($O(N \times M)$).
  - *Safe key access:* The starter code crashed or gave wrong results when orders had `total_paise` instead of `amount_paise`.
- **Evidence:**
  - 20 parameterized tests in `test_acceptance_matrix.py` test replaying events.
  - The dataset in `data/records.json` has 150 internal orders and 163 provider records. Using dictionaries keeps reconciliation instantaneous.

---

## 2. Options considered

### Option 1: Changing `processed_event_ids` from a list to a set
- **Expected benefit:** $O(1)$ lookup for `if event_id in out["processed_event_ids"]`.
- **Risk / Drawback:**
  - Python `set` is not JSON serializable (`json.dumps()` raises `TypeError`).
  - The starter contract in `models.py` explicitly defines `"processed_event_ids": []` as a list.
  - A set loses the insertion order of events.
- **Why rejected:** In a food delivery app, an order only goes through a handful of events (typically 3 to 6 events: payment, accept, dispatch, deliver/cancel, refund). Searching an `in` list of 5 strings takes a fraction of a microsecond. Keeping it as a list preserves the event history and allows easy JSON serialization without breaking the contract.

### Option 2: Using `deepcopy` vs shallow `copy()`
- **Expected benefit of shallow copy:** Shallow copying (`dict(order)`) is faster than `deepcopy(order)`.
- **Risk / Drawback:** Because `order` contains a nested list `processed_event_ids`, a shallow copy would still point to the original list. Modifying `out["processed_event_ids"]` would mutate the input `order["processed_event_ids"]`, breaking `test_input_order_is_not_mutated`.
- **Why rejected:** Preserving input immutability is essential for pure functions, so `deepcopy` was the correct choice.

---

## 3. Changes implemented
- **Change 1: Early idempotency return**
  - *Reason:* If `event_id` is already in `processed_event_ids`, return `out` immediately.
  - *Tests protecting it:* `test_payment_event_replay_idempotent`, `test_duplicate_event_with_same_id_is_ignored`.
  - *Measurement:* Running all 222 tests takes only ~1.06s.

- **Change 2: Dictionary indexing for reconciliation**
  - *Reason:* Built `left` and `right` dictionaries keyed by `order_id`. This allows $O(1)$ lookups when comparing records rather than searching through the lists repeatedly.
  - *Tests protecting it:* `test_reconciliation_results_are_deterministic`, `test_records_json_dataset`.

- **Change 3: Stretch task CSV export (`export_awaiting_refund_csv`)**
  - *Reason:* Implemented a single-pass filter over the orders list to export records where `refund_due_paise > refunded_paise`.
  - *Tests protecting it:* `test_export_awaiting_refund_csv`.

---

## 4. Trade-offs
- **Simplicity vs FSM libraries:**
  Instead of importing or building an abstract finite state machine class, I used clear `if/elif` statements checking `out.get("status")`. It is straightforward to read, easy to debug, has no external dependencies, and is completely self-contained.
- **`deepcopy` overhead:**
  `deepcopy` has a small performance cost, but it guarantees that the caller's input dictionary is never accidentally modified.

---

## 5. Further improvements
- **Batching and streaming for large files:**
  If we were reconciling millions of transactions every day (like Zomato does across multiple payment gateways), loading the entire JSON file into RAM with `json.load()` could cause memory issues. A good future optimization would be streaming the records in chunks using a streaming parser (like `ijson`) or storing them temporarily in an SQLite database and querying the differences with SQL `LEFT JOIN`.
