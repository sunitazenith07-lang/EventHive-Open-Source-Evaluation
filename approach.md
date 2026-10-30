# approach.md - Required submission

## 1. Baseline
- **Commands run before editing:**
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result:**
  - `62 failed, 150 passed in 0.09s` (out of 212 tests).
- **Demo/output observed:**
  - `matched: []`, `missing_from_provider: ['ORD-103']`, `missing_from_internal: ['ORD-104']`, `amount_mismatches: ['ORD-101', 'ORD-102']`, `status_mismatches: []`.
  - Noticeably, `ORD-101` should have matched and `ORD-102` should have been a status mismatch, not an amount mismatch.

## 2. Codebase understanding
- **Important files and functions inspected:**
  - `service.py`: contains `apply_order_event` and `reconcile_orders`.
  - `models.py` & `fixtures.py`: creates order dicts with `new_order`.
  - `tests/test_contract.py` & `tests/test_acceptance_matrix.py`: checked what the failing assertions were testing.
- **Order lifecycle or data flow traced:**
  - Orders start as `PLACED` and `UNPAID`. Normal path: `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`.
  - Orders can only be rejected when `PLACED`, and cancelled when `PLACED` or `ACCEPTED` (before dispatch).
  - If a paid order gets rejected or cancelled, `refund_due_paise` is set to `total_paise`.
- **How you confirmed your understanding:**
  - Read the assertions in `tests/` and ran `python -m main` to compare the starter output with `fixtures.py`.

## 3. Investigation and implementation strategy
- **Issue 1: Duplicate events were not ignored (Idempotency)**
  - *Symptom:* `test_payment_event_replay_idempotent` failed because `processed_event_ids` had `['EV-000', 'EV-000']` instead of `['EV-000']`.
  - *Hypothesis:* `apply_order_event` wasn't checking if `event_id` was already in `processed_event_ids` before running.
  - *Fix:* Added an `if event_id is not None and event_id in out["processed_event_ids"]: return out` check right at the start, and only appended `event_id` if it's not `None`.
- **Issue 2: Refunds had no validation**
  - *Symptom:* Tests for negative/invalid amounts, ineligible statuses, and over-refunding all failed.
  - *Hypothesis:* The `refund_processed` block just added `amount_paise` directly without checking order status, amount type, or remaining refund due.
  - *Fix:* Checked that `status` is `REJECTED` or `CANCELLED`, `payment_status` is `PAID`, and `refund_due_paise > 0`. Also checked that `amount` is a positive integer (and not a `bool`) and `<= refund_due_paise - refunded_paise`. Only set `payment_status = "REFUNDED"` when `refunded_paise == refund_due_paise`.
- **Issue 3: Reconciliation missed status mismatches and `total_paise`**
  - *Symptom:* `test_reconciliation_status_mismatch_matrix` failed and `main.py` put `ORD-101` in `amount_mismatches`.
  - *Hypothesis:* Internal orders from `new_order()` use `total_paise` while provider orders use `amount_paise`, so `a.get("amount_paise")` returned `None`. Also, `status` wasn't compared at all.
  - *Fix:* Checked `amount_paise` first, falling back to `total_paise`. Added a separate check for `a.get("status") != b.get("status")` to populate `status_mismatches`.

## 4. Implementation decisions
- **Main changes and why:**
  - Updated `apply_order_event` and `reconcile_orders` in `service.py` to handle idempotency, refund rules, late payments on rejected/cancelled orders, and status/amount reconciliation.
  - Added `summarise_orders_by_state` as the optional stretch goal.
- **Alternatives considered and why rejected:**
  - Thought about raising `ValueError` for bad refund amounts, but the tests expect the function to ignore invalid events and return the unchanged order dict.
- **Assumptions:**
  - Amounts are always in integer paise.
  - Once an order is `OUT_FOR_DELIVERY`, customer cancellation requests are ignored.

## 5. Verification
- **Tests added or changed:**
  - Added `tests/test_regression.py` with 18 tests covering idempotency, invalid refund types, split refunds, late payment confirmation, and reconciliation mismatches. Did not modify existing tests.
- **Commands run and actual results:**
  - `python -m pytest -q` -> `230 passed in 0.08s`.
  - `python -m main` -> `matched: ['ORD-101']`, `missing_from_provider: ['ORD-103']`, `missing_from_internal: ['ORD-104']`, `amount_mismatches: []`, `status_mismatches: ['ORD-102']`.
- **Edge cases verified:**
  - `True`/`False` passed as refund amounts, duplicate event IDs, partial refunds adding up to full refund, and simultaneous amount + status mismatches.
- **Remaining failures or known limitations:**
  - None. All 230 tests pass.
