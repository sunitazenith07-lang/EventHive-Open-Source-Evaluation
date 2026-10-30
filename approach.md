# approach.md - Required submission

## 1. Baseline
- **Commands run before editing:**
  - `python --version` -> Python 3.13.15
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result:**
  - `62 failed, 150 passed in 2.45s` (out of 212 tests total).
  - Main test failures:
    - 20 failures in `test_payment_event_replay_idempotent` where replaying `payment_confirmed` resulted in `['EV-000', 'EV-000']` instead of `['EV-000']`.
    - 13 failures in `test_invalid_refund_amounts_are_ignored` (negative amounts, floats, `None`, strings, and `True`/`False` were not filtered out).
    - 10 failures in `test_refund_eligibility_matrix` because refunds were processed on orders that were not cancelled/rejected or unpaid.
    - 7 failures in `test_refunds_cannot_exceed_due`.
    - 7 failures in `test_reconciliation_status_mismatch_matrix` because status differences were ignored.
- **Demo output observed:**
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  `ORD-101` and `ORD-102` were wrongly listed under amount mismatches, and status mismatches were empty even though `ORD-102` had different statuses.

---

## 2. Codebase understanding
- **Important files and functions inspected:**
  - `service.py`: Contains `apply_order_event()` for state transitions and `reconcile_orders()` for comparing internal vs provider lists.
  - `models.py`: Defines `new_order()`. The dictionary uses keys `order_id`, `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise`, and `processed_event_ids`.
  - `fixtures.py`: Provides sample orders for the demo. I noticed internal orders use `total_paise` while provider orders use `amount_paise`.
  - `main.py`: Runs `reconcile_orders(sample_orders(), sample_provider_orders())` and prints the output.
  - `tests/test_acceptance_matrix.py` & `tests/test_contract.py`: The test suites defining expected transitions, refund rules, and reconciliation outputs.
- **Order lifecycle traced:**
  - Order starts as `PLACED` with `payment_status="UNPAID"`.
  - Payment can be confirmed (`payment_confirmed`), setting `payment_status="PAID"`. If the order was already rejected or cancelled before payment arrived, `refund_due_paise` should become `total_paise`.
  - Normal flow: `PLACED` -> `restaurant_accepted` (`ACCEPTED`) -> `dispatch_started` (`OUT_FOR_DELIVERY`) -> `order_delivered` (`DELIVERED`).
  - Cancellation: Customer can cancel (`cancel_requested`) only while the order is in `PLACED` or `ACCEPTED`. If already dispatched or delivered, cancellation requests must be ignored.
  - Rejection: Restaurant can reject (`restaurant_rejected`) only while `PLACED`.
  - If cancelled or rejected after payment, `refund_due_paise` is set to `total_paise`.
  - Refunds (`refund_processed`): Only allowed on `CANCELLED` or `REJECTED` orders that are `PAID`. Amount must be a positive integer and cannot exceed `refund_due_paise - refunded_paise`. Status turns `REFUNDED` only when full due amount is refunded.
- **How I confirmed my understanding:**
  - I traced failing tests individually with `-k <test_name>` and examined the assertions in `test_acceptance_matrix.py`.

---

## 3. Investigation and implementation strategy

### Issue 1: Idempotency was completely missing
- **Symptom:** `test_payment_event_replay_idempotent` failed because `processed_event_ids` contained duplicate event IDs.
- **Hypothesis:** `apply_order_event` was simply doing `out["processed_event_ids"].append(event_id)` at the very bottom without checking if `event_id` was already in the list.
- **Evidence:** `assert twice["processed_event_ids"] == [event_id]` failed with `['EV-000', 'EV-000'] == ['EV-000']`.
- **Fix:** Added an early check at the top of `apply_order_event`:
  ```python
  event_id = event.get("event_id")
  if event_id is not None and event_id in out["processed_event_ids"]:
      return out
  ```
  Also made sure to only append `event_id` if it is not `None` and not already in `processed_event_ids`.

### Issue 2: Refunds had no validation and overflowed
- **Symptom:** Invalid refund amounts (floats, negative ints, booleans, excessive amounts) were accepted, and unpaid or active orders could be refunded.
- **Hypothesis:** The starter code just did `out["refunded_paise"] += event.get("amount_paise", 0)`. When `refund_due_paise` was 0, `0 >= 0` evaluated to true, so it set `payment_status="REFUNDED"` immediately!
- **Evidence:** `test_invalid_refund_amounts_are_ignored`, `test_refund_eligibility_matrix`, and `test_refunds_cannot_exceed_due` all failed.
- **Fix:**
  1. Check eligibility: `status in ("REJECTED", "CANCELLED")` and `payment_status == "PAID"` and `(due - refunded) > 0`.
  2. Validate amount: `type(amount) is int and amount > 0 and amount <= (due - refunded)`. (Used `type(amount) is int` so booleans like `True` are rejected).
  3. Increment `refunded_paise`, and only set `payment_status="REFUNDED"` if `refunded_paise >= due`.

### Issue 3: Reconciliation missed status differences and key name difference
- **Symptom:** Status mismatches were ignored, and in `main.py` orders were falsely flagged as amount mismatches.
- **Hypothesis:**
  1. `service.py` had an explicit comment saying status mismatches weren't implemented.
  2. `sample_orders()` has `total_paise` while `sample_provider_orders()` has `amount_paise`. The code did `a.get("amount_paise")`, which returned `None` for internal orders.
- **Evidence:** In `main.py`, `ORD-101` has amount 45900 on both sides, but showed up in `amount_mismatches`.
- **Fix:**
  - Read amount using `a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")` for both sides.
  - Added separate checks for `has_amount_diff` and `has_status_diff`. If both happen, the order ID gets added to both mismatch lists, and it is excluded from `matched`.

---

## 4. Implementation decisions
- **Main changes:**
  - Used `deepcopy(order)` to ensure we return a new order copy and never mutate the caller's dictionary.
  - Handled missing or non-dict inputs cleanly without raising unhandled exceptions.
  - Implemented the optional stretch task: `export_awaiting_refund_csv()` to export a CSV of orders where `refund_due_paise > refunded_paise`.
- **Alternatives considered:**
  - *Using `isinstance(amount, int)`:* Python's `bool` is a subclass of `int`, so `isinstance(True, int)` is True. This failed `test_invalid_refund_amounts_are_ignored[True]`. So I used `type(amount) is int`.
  - *Using `set` for `processed_event_ids`:* Sets are not JSON serializable and break the model contract (`processed_event_ids: []`). Since an order only has a few events, checking membership in a small list is fast and keeps the order of events intact.
- **Assumptions:**
  - Events with missing `order_id` apply to the order passed to `apply_order_event`. If an event has an explicit `order_id` that doesn't match the order's `order_id`, it is safely ignored.

---

## 5. Verification
- **Tests added:** Added 10 tests in `tests/test_regression_and_edge_cases.py` covering late cancellation, event replay, late payment after rejection, boolean amounts, multi-step refunds, reconciliation with `data/records.json`, and the CSV export function.
- **Actual test results:**
  - `python -m pytest -q` -> `222 passed in 1.06s`
  - `python -m main`:
    ```text
    matched: ['ORD-101']
    missing_from_provider: ['ORD-103']
    missing_from_internal: ['ORD-104']
    amount_mismatches: []
    status_mismatches: ['ORD-102']
    ```
- **Remaining failures:** None.
