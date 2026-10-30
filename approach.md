# approach.md - Required submission

## 1. Baseline
- **Commands run before editing:**
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result:**
  - Out of 212 visible tests, **62 failed and 150 passed** in 0.60s.
  - The failures fell into three clear areas:
    - 21 tests failed because replayed events were processed again and duplicated event IDs into `processed_event_ids`.
    - 33 tests failed because refunds lacked basic checks (allowing negative numbers, boolean values, over-refunding, or refunding unpaid orders).
    - 8 tests failed in reconciliation because status differences were completely ignored.
- **Demo output observed (`python -m main`):**
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  `ORD-101` was reported as an amount mismatch even though both internal and provider showed 45900 paise. Looking at the code, internal orders used the dictionary key `total_paise` while the provider used `amount_paise`. Also, `ORD-102` had mismatched statuses (`ACCEPTED` vs `CANCELLED`), but `status_mismatches` was empty.

## 2. Codebase understanding
- **Important files and functions inspected:**
  - `service.py`: Contains `apply_order_event` (lifecycle and refund logic) and `reconcile_orders` (reconciliation logic).
  - `models.py`: Helper `new_order` which sets up the baseline order dictionary.
  - `fixtures.py` and `main.py`: Sample data and demo script.
  - `data/records.json`: Synthetic dataset with 150 orders, 163 provider records, and 219 event examples.
  - `tests/test_acceptance_matrix.py` and `tests/test_contract.py`: 212 tests defining the expected system behavior.
- **Order lifecycle traced:**
  - Normal flow: `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`.
  - Cancellation and Rejection: An order can be cancelled while in `PLACED` or `ACCEPTED`. Once it reaches `OUT_FOR_DELIVERY` or `DELIVERED`, customer cancellation is no longer allowed. A restaurant can reject an order while it is `PLACED`.
  - Payment and Refunds: When an order is paid and then cancelled or rejected, `refund_due_paise` equals `total_paise`. Refunds accumulate in `refunded_paise`. The payment status only becomes `REFUNDED` once the full amount due has been repaid.
- **How I confirmed my understanding:**
  I ran pytest with `-k` to reproduce individual failing tests, checked their inputs, and traced the execution path through `service.py`.

## 3. Investigation and implementation strategy

- **Issue 1: Duplicate events broke idempotency**
  - *What went wrong:* When the same event arrived a second time, the code ran the transition again and appended the event ID twice (`['e1', 'e1']`).
  - *Evidence:* Tests like `test_duplicate_event_is_idempotent` failed with `AssertionError: assert ['e1', 'e1'] == ['e1']`.
  - *Fix:* At the start of `apply_order_event`, I added an idempotency check: if `event_id` is already in `processed_event_ids`, return the order dictionary immediately without making any changes.

- **Issue 2: Refunds had no validation**
  - *What went wrong:* Any `refund_processed` event was added straight to `refunded_paise`, even if the order was unpaid or active, or if the amount was negative, a boolean, or exceeded the amount due.
  - *Evidence:* In Python, `bool` is a subclass of `int` (`isinstance(True, int)` is `True`), so passing `True` refunded 1 paise. Also, amounts like 6000 were accepted on an order that only owed 5000.
  - *Fix:* I added three checks before applying a refund:
    1. Order must be `CANCELLED` or `REJECTED`, payment status must be `PAID`, and `refund_due_paise` must be greater than 0.
    2. The amount must be a positive integer, explicitly excluding booleans (`isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`).
    3. The amount cannot exceed what is left to refund (`refund_due_paise - refunded_paise`).

- **Issue 3: Reconciliation ignored status differences and missed amount keys**
  - *What went wrong:* `reconcile_orders` never checked `status` differences, so mismatched orders ended up in `matched`. It also only checked `amount_paise`, missing internal orders that store amounts under `total_paise`.
  - *Evidence:* `test_reconcile_reports_status_difference` failed because `status_mismatches` was empty and `matched` had the order instead.
  - *Fix:* I added a helper to check both `amount_paise` and `total_paise`, compared amount and status differences separately, and only marked an order as `matched` if both matched.

## 4. Implementation decisions
- **Main changes and why:**
  - Kept the function pure using `deepcopy(order)` so the original order dictionary is never mutated in place.
  - Handled late payment confirmations: if payment confirms after an order was already cancelled or rejected, `refund_due_paise` is updated to `total_paise` so the customer gets their refund.
  - Guarded against malformed input (like `None` or non-dict events) to avoid unhandled crashes.
- **Alternatives considered and why rejected:**
  - I considered using a `set` for `processed_event_ids` for $O(1)$ lookup, but kept it as a `list` because the existing tests and JSON output expect a list.
  - I considered raising exceptions for invalid refund events, but the problem statement prefers ignoring invalid events cleanly without crashing.
- **Assumptions:**
  - All monetary values are in integer paise (no decimal rupees).
  - Customers cannot cancel an order after the rider has picked it up (`OUT_FOR_DELIVERY`).

## 5. Verification
- **Tests added:**
  I kept all 212 existing tests untouched and added a new test file `tests/test_regression_edge_cases.py` with 7 edge cases covering late payments, boolean amounts, multi-step partial refunds, post-dispatch cancellations, and malformed events.
- **Commands run and results:**
  - `python -m pytest -q`: All 219 tests passed (0 failures).
  - `python -m main`: The demo output now correctly places `ORD-101` in `matched` and `ORD-102` in `status_mismatches`.
- **Known limitations:**
  - State and processed event IDs are kept in memory inside the order dictionary. In a real-world multi-server backend, we would use a database transaction or a distributed lock (like Redis) to handle concurrent requests safely.