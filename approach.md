# approach.md - Required submission

## 1. Baseline
- **Commands run before editing:**
  - `python --version` -> `Python 3.13.15`
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result (include the actual summary):**
  - `62 failed, 150 passed, 2 warnings in 0.43s` (out of 212 collected tests across `tests/test_contract.py` and `tests/test_acceptance_matrix.py`).
- **Demo/output observed:**
  - Running `python -m main` on the untouched starter produced:
    ```text
    matched: []
    missing_from_provider: ['ORD-103']
    missing_from_internal: ['ORD-104']
    amount_mismatches: ['ORD-101', 'ORD-102']
    status_mismatches: []
    ```
  - Even though `ORD-101` (`45900` paise, `PLACED`) matched the provider record and `ORD-102` (`129900` paise, `ACCEPTED` vs `CANCELLED`) was a status mismatch, both were falsely categorized under `amount_mismatches`.

## 2. Codebase understanding
- **Important files and functions inspected:**
  - `models.py`: Defines `new_order(order_id, total_paise, status="PLACED")`, initializing an order dictionary with `total_paise`, `status`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, and `processed_event_ids=[]`.
  - `service.py`: Contains `apply_order_event(order, event)` for order state transitions, idempotency, and refund processing, and `reconcile_orders(internal, provider)` for order summary comparison.
  - `fixtures.py` & `main.py`: Feed synthetic orders (`ORD-101` to `ORD-104`) into `reconcile_orders`.
  - `data/records.json` & `data/README.txt`: Contains 150 internal orders, 163 provider records, 219 event payloads, and a 12-item `reconciliation_edge_cases` catalog.
  - `tests/test_contract.py` & `tests/test_acceptance_matrix.py`: 212 unit and parameterized contract tests verifying transitions, idempotency, refund bounds, and reconciliation.
- **Order lifecycle or data flow traced:**
  - Orders start at `PLACED` (`UNPAID`). `payment_confirmed` sets `payment_status = "PAID"`.
  - From `PLACED`, an order can transition to `ACCEPTED` (`restaurant_accepted`), `REJECTED` (`restaurant_rejected`), or `CANCELLED` (`cancel_requested`).
  - From `ACCEPTED`, an order can transition to `CANCELLED` (`cancel_requested`) or `OUT_FOR_DELIVERY` (`dispatch_started`). Once `OUT_FOR_DELIVERY`, `cancel_requested` is ignored and only `order_delivered` transitions it to `DELIVERED`.
  - When a `PAID` order transitions to `REJECTED` or `CANCELLED` (or when `payment_confirmed` arrives for an `UNPAID` order already in `REJECTED`/`CANCELLED`), `refund_due_paise` is set to `total_paise`. Eligible `refund_processed` events accumulate positive integer paise in `refunded_paise` up to `refund_due_paise`, setting `payment_status = "REFUNDED"` only when `refunded_paise == refund_due_paise`.
- **How you confirmed your understanding:**
  - Cross-referenced the 62 failing assertions in `pytest -v` with the starter code in `service.py` and the 219 synthetic events in `data/records.json`.

## 3. Investigation and implementation strategy
- **Issue 1: Missing event idempotency (21 failing tests)**
  - *Symptom:* `test_duplicate_event_is_idempotent` and `test_payment_event_replay_idempotent[EV-000..EV-019]` failed with `AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']`.
  - *Hypothesis & Evidence:* `apply_order_event` appended `event_id` at the end of the function without checking if `event_id` was already in `out["processed_event_ids"]`.
  - *Fix chosen:* Validate that `event_id` is a non-empty, non-boolean value; if `event_id in out["processed_event_ids"]`, immediately return `out` without mutating state or appending `event_id` again.
- **Issue 2: Unsafe refund processing—eligibility, type validation, and upper bounds (33 failing tests)**
  - *Symptom:* `test_refund_requires_eligible_order` (11 failures), `test_invalid_refund_amounts_are_ignored` (14 failures, including `amount_paise=True`, `-10`, `0.5`), and `test_refunds_cannot_exceed_due` (8 failures).
  - *Hypothesis & Evidence:* In Python, `isinstance(True, int)` evaluates to `True`, and `service.py` unconditionally ran `out["refunded_paise"] += event.get("amount_paise", 0)` without checking order status, payment status, integer type, positivity, or remaining refundable balance.
  - *Fix chosen:* Added `_is_strict_int(val)` (`isinstance(val, int) and not isinstance(val, bool)`), restricted refunds to orders where `status in ("REJECTED", "CANCELLED")`, `payment_status == "PAID"`, and `refund_due_paise > 0`, and required `0 < amount <= (refund_due_paise - refunded_paise)`.
- **Issue 3: Reconciliation status mismatch blindness and field discrepancy (8 failing tests + demo anomaly)**
  - *Symptom:* `test_reconcile_reports_status_difference` and `test_reconciliation_status_mismatch_matrix` failed because orders with matching amounts but different statuses were placed in `matched`. Furthermore, `main.py` reported `ORD-101` and `ORD-102` in `amount_mismatches`.
  - *Hypothesis & Evidence:* `reconcile_orders` used `if a.get("amount_paise") != b.get("amount_paise"): ... else: report["matched"].append(key)`, never comparing `status`. Additionally, `new_order()` in `models.py` stores `"total_paise"`, whereas provider records and matrix tests use `"amount_paise"`, making `a.get("amount_paise")` evaluate to `None` in `main.py`.
  - *Fix chosen:* Extracted amounts via `r.get("amount_paise") if "amount_paise" in r else r.get("total_paise")` and evaluated `amt_mismatch` and `status_mismatch` independently so orders with amount differences, status differences, or both are deterministically reported in their respective lists, and added to `matched` only when neither mismatch occurs.

## 4. Implementation decisions
- **Main changes and why:**
  - Updated `apply_order_event` and `reconcile_orders` in `service.py` and added `_is_strict_int` and `summarize_orders_by_state` (optional stretch item).
  - Added late-payment handling in `payment_confirmed`: if an `UNPAID` order was already `REJECTED` or `CANCELLED` before payment confirmation arrived, confirming payment sets `payment_status = "PAID"` and `refund_due_paise = total_paise`.
- **Alternatives considered and why rejected:**
  - Considered changing `new_order()` in `models.py` to rename `total_paise` to `amount_paise`, but rejected this because internal orders in `data/records.json` and existing tests rely on `total_paise`. Supporting `amount_paise` with fallback to `total_paise` in `reconcile_orders` maintains 100% backward compatibility.
- **Assumptions:**
  - Events without an `event_id` (such as 7 events in `data/records.json`) are processed once if valid, without appending `None` or `""` to `processed_event_ids`.
  - An invalid or out-of-bounds event is a no-op on order state and refund balances, while still recording its valid `event_id` as seen.

## 5. Verification
- **Tests added or changed:**
  - Preserved all 212 existing tests untouched and added 8 new tests in `tests/test_contract.py` (7 regression tests + 1 test for `summarize_orders_by_state`).
- **Commands run and actual results:**
  - `python -m pytest -q` -> `220 passed, 1 warning in 0.18s`
  - `python -m main` -> `matched: ['ORD-101']`, `missing_from_provider: ['ORD-103']`, `missing_from_internal: ['ORD-104']`, `amount_mismatches: []`, `status_mismatches: ['ORD-102']`.
- **Edge cases verified:**
  - Conflicting duplicate `event_id` replay, sequential partial refunds + over-refund blocking, late `payment_confirmed` after rejection/cancellation, boolean/non-int refund rejection, simultaneous amount + status mismatch, malformed/None inputs, and full replay of `data/records.json`.
- **Remaining failures or known limitations:**
  - Zero failing tests (`220 passed`). Processing is in-memory per order dictionary; cross-process persistence would require transactional database storage.
