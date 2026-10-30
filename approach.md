# approach.md - Required submission

## 1. Baseline
- **Commands run before editing:**
  - `python --version` -> Python 3.13.15
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result (actual summary):**
  - `62 failed, 150 passed in 0.55s` (Total: 212 tests across `test_acceptance_matrix.py` and `test_contract.py`).
- **Demo/output observed (`python -m main`):**
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  *Analysis of baseline demo:* `ORD-101` and `ORD-102` were incorrectly classified under `amount_mismatches` because internal records use the key `total_paise` while provider records use `amount_paise`. Furthermore, `ORD-102` had a status mismatch (`ACCEPTED` vs `CANCELLED`) that was completely omitted because the starter code did not evaluate status differences.

## 2. Codebase understanding
- **Important files and functions inspected:**
  - `service.py`: `apply_order_event(order, event)` and `reconcile_orders(internal, provider)`.
  - `models.py`: `new_order(order_id, total_paise, status)` initializing order state dictionary.
  - `fixtures.py` & `main.py`: Demo sample records and offline verification script.
  - `tests/test_acceptance_matrix.py` & `tests/test_contract.py`: Acceptance test suites enforcing idempotency, refund limits, transition safety, and deterministic reconciliation.
  - `data/records.json` & `data/README.txt`: 150 synthetic orders, 163 provider records, 219 event examples, and the 12-item edge-case catalog.
- **Order lifecycle or data flow traced:**
  - Order starts with `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, and `processed_event_ids=[]`.
  - Transition events:
    - `payment_confirmed`: Sets `payment_status="PAID"`. If already rejected/cancelled, initiates `refund_due_paise = total_paise`.
    - `restaurant_accepted`: Allowed only from `PLACED` -> `ACCEPTED`.
    - `restaurant_rejected`: Allowed only from `PLACED` -> `REJECTED`. If paid, sets `refund_due_paise = total_paise`.
    - `cancel_requested`: Allowed from `PLACED` or `ACCEPTED` -> `CANCELLED`. If paid, sets `refund_due_paise = total_paise`. Ignored if already dispatched or delivered.
    - `dispatch_started`: Allowed from `ACCEPTED` -> `OUT_FOR_DELIVERY`.
    - `order_delivered`: Allowed from `OUT_FOR_DELIVERY` -> `DELIVERED`.
    - `refund_processed`: Only valid if order is in `CANCELLED` or `REJECTED` state, `payment_status == "PAID"`, and positive integer amount <= outstanding refundable amount (`refund_due_paise - refunded_paise`). Marks `payment_status="REFUNDED"` only upon reaching full due amount.
- **How understanding was confirmed:**
  - Traced failing test parameters in `test_acceptance_matrix.py`, verified event schemas in `data/records.json`, and reviewed assertions in `test_contract.py`.

## 3. Investigation and implementation strategy
- **Issue 1: Missing event idempotency in `apply_order_event`**
  - *Symptom:* 20 tests in `test_payment_event_replay_idempotent` and `test_duplicate_event_is_idempotent` failed with `AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']`.
  - *Hypothesis:* The starter code unconditionally executed `out["processed_event_ids"].append(event_id)` without checking if `event_id` was already in `out["processed_event_ids"]`.
  - *Fix:* Added an idempotency guard at the function entry: `if event_id is not None and event_id in out["processed_event_ids"]: return out`.
- **Issue 2: Unsafe refund processing (invalid types, negative amounts, over-refunding, ineligible states)**
  - *Symptom:* 30 tests failed across `test_invalid_refund_amounts_are_ignored`, `test_refund_eligibility_matrix`, `test_refunds_cannot_exceed_due`, and contract refund tests.
  - *Hypothesis:* `service.py` added `event.get("amount_paise", 0)` without verifying that the order is in `REJECTED` or `CANCELLED` status with `payment_status == "PAID"`, without checking strict integer type (`type(amount) is int and not bool`), and without checking `amount <= outstanding_due`.
  - *Fix:* Enforced order eligibility check (`status in ("REJECTED", "CANCELLED") and payment_status == "PAID" and refund_due_paise > 0`), strict positive integer type validation (`type(amount) is int and amount > 0`), and outstanding cap check (`refunded_paise + amount <= refund_due_paise`). Payment status only changes to `REFUNDED` when `refunded_paise >= refund_due_paise`.
- **Issue 3: Defective reconciliation and field mismatch in `reconcile_orders`**
  - *Symptom:* 8 tests failed in `test_reconciliation_status_mismatch_matrix` and contract tests; `main.py` falsely reported amount mismatches.
  - *Hypothesis:* Records could store the order amount under `amount_paise` or `total_paise`. The starter only checked `a.get("amount_paise")`, which evaluated to `None` for standard internal orders. Furthermore, if amounts matched, it unconditionally added the ID to `matched` without checking status.
  - *Fix:* Created a unified amount extractor (`a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")`). Evaluated `amount_match` and `status_match` independently. Flagged mismatches into `amount_mismatches` and `status_mismatches` respectively, adding to `matched` only when both match.

## 4. Implementation decisions
- **Main changes and why:**
  - Implemented immutable state updates via `deepcopy` while ensuring defensive validation for empty/malformed inputs.
  - Handled out-of-order `payment_confirmed` events (activating `refund_due_paise` if order had already been cancelled/rejected prior to payment confirmation).
  - Implemented `export_awaiting_refund_csv` as the optional stretch feature for reporting orders requiring refunds.
- **Alternatives considered and why rejected:**
  - *In-place mutation:* Rejected because `apply_order_event` must preserve functional immutability and pass `test_input_order_is_not_mutated`.
  - *Raising exceptions for invalid events/refunds:* Rejected because food-delivery event pipelines must gracefully ignore invalid/duplicate events without crashing or corrupting state.
- **Assumptions:**
  - Paise values are non-negative integers; amounts cannot be fractional or boolean.
  - Orders can only be refunded if previously paid and cancelled/rejected.

## 5. Verification
- **Tests added or changed:**
  - Kept all existing tests in `test_acceptance_matrix.py` and `test_contract.py` unchanged.
  - Added `tests/test_regression.py` containing 11 comprehensive test functions covering edge cases from `records.json` and stretch functionality.
- **Commands run and actual results:**
  - `python -m pytest -q` -> `223 passed in 0.18s` (0 failures, 0 errors).
  - `python -m main` -> Correctly outputs:
    `matched: ['ORD-101']`
    `missing_from_provider: ['ORD-103']`
    `missing_from_internal: ['ORD-104']`
    `amount_mismatches: []`
    `status_mismatches: ['ORD-102']`
- **Edge cases verified:**
  - Replay of payment and refund event IDs.
  - Cancellation after dispatch ignored.
  - Booleans (`True`/`False`), floats, strings, None in refund amount.
  - Over-refunding beyond `refund_due_paise`.
  - Simultaneous status and amount mismatches in reconciliation.
  - Processing synthetic dataset `data/records.json` (150 orders, 219 events, 163 provider records).
- **Remaining failures or known limitations:**
  - None. All 223 tests pass cleanly.
