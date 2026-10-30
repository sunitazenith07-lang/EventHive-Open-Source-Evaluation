# optimizations.md - Required submission

## 1. Baseline and objective
- **What needed improvement:**
  - Avoid re-running transition logic when duplicate events arrive.
  - Avoid unnecessary `deepcopy` work when inputs are empty or invalid.
  - Keep `reconcile_orders` fast and clean when comparing larger lists (like the 150 orders and 163 provider records in `data/records.json`).
- **Evidence:**
  - In the starter code, duplicate events still ran through the `if/elif` chain and appended to `processed_event_ids`.

## 2. Options considered
- **Option 1: Early return on duplicate `event_id` and invalid inputs (Implemented)**
  - *Benefit:* Skips the transition checks immediately if the event was already processed, and skips `deepcopy` if `order` isn't a dict.
  - *Risk:* None.
- **Option 2: Converting `processed_event_ids` from a `list` to a `set` (Rejected)**
  - *Benefit:* `O(1)` lookup time instead of `O(n)` list scan.
  - *Why rejected:* The tests check `assert twice["processed_event_ids"] == [event_id]` (expecting a list in order), and a single order only has around 5–10 events anyway, so a list check is already tiny and avoids extra type conversions.
- **Option 3: Dictionary lookup in `reconcile_orders` (Kept & improved)**
  - *Benefit:* Indexing `internal` and `provider` by `order_id` in dicts is `O(N + M)` instead of `O(N * M)` nested loops.

## 3. Changes implemented
- **Change:** Added early return guards at the top of `apply_order_event` and single-pass dictionary indexing in `reconcile_orders` and `summarise_orders_by_state`.
- **Reason:** Keeps the code simple, readable, and avoids wasted work on duplicate/bad events.
- **Tests used to protect correctness:** All 230 tests in `tests/test_acceptance_matrix.py`, `tests/test_contract.py`, and `tests/test_regression.py`.
- **Measurement method and result:** Ran `pytest -q`; all 230 tests (including reconciling the full `data/records.json` dataset) finished in `0.08s`.

## 4. Trade-offs
- Using `deepcopy(order)` on every call uses a bit more memory than mutating the dict in place, but it is required so we never accidentally modify the caller's original order dictionary (verified by `test_input_order_is_not_mutated`).

## 5. Further improvements
- If an order could receive thousands of events, we could store a separate `set` alongside the list for `O(1)` idempotency checks while keeping the ordered list for history.
