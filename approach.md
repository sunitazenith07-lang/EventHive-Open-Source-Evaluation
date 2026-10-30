# approach.md - Required submission

## 1. Baseline
- **Commands run before editing:**
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result (actual summary):**
  - 62 failed, 150 passed in 1.18s (212 total collected items)
  - Failures occurred across `test_payment_event_replay_idempotent`, `test_invalid_refund_amounts_are_ignored`, `test_refund_eligibility_matrix`, `test_refunds_cannot_exceed_due`, `test_reconciliation_status_mismatch_matrix`, `test_duplicate_event_is_idempotent`, `test_refund_requires_eligible_order`, `test_refund_must_be_positive`, `test_refund_cannot_exceed_amount_due`, and `test_reconcile_reports_status_difference`.
- **Demo/output observed (`python -m main`):**
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  Note that ORD-101 (amount 45900, status PLACED) was misreported as an amount mismatch because internal orders used `total_paise` rather than `amount_paise`, and ORD-102 (status ACCEPTED vs CANCELLED) was also erroneously flagged as amount mismatch and omitted from status mismatches.

## 2. Codebase understanding
- **Important files and functions inspected:**
  - `service.py`: `apply_order_event(order, event)` (state transitions, idempotency, refund processing), `reconcile_orders(internal, provider)` (reconciliation engine).
  - `models.py`: `new_order(order_id, total_paise, status)` (dictionary schema for internal orders).
  - `fixtures.py` & `main.py`: Sample data fixtures and offline reconciliation demo.
  - `tests/test_acceptance_matrix.py` & `tests/test_contract.py`: Matrix parametrization for transitions, replay idempotency, refund bounds, and reconciliation.
  - `data/records.json` & `data/README.txt`: 150 synthetic orders, 163 provider records, 219 event records, and reconciliation edge-case catalog.
- **Order lifecycle or data flow traced:**
  - Orders begin at `PLACED` with `payment_status="UNPAID"`.
  - Payment confirmation sets `payment_status="PAID"`. If the order was already rejected or cancelled, full refund becomes due immediately (`refund_due_paise = total_paise`).
  - Restaurant acceptance transitions `PLACED -> ACCEPTED`. Rejection transitions `PLACED -> REJECTED` (with full `refund_due_paise = total_paise` if paid).
  - Cancellation is only valid from `PLACED` or `ACCEPTED` -> `CANCELLED` (with full `refund_due_paise = total_paise` if paid). Cancellation after dispatch is rejected.
  - Dispatch transitions `ACCEPTED -> OUT_FOR_DELIVERY`, and final delivery transitions `OUT_FOR_DELIVERY -> DELIVERED`.
  - Refund processing requires `status in ("REJECTED", "CANCELLED")`, `payment_status == "PAID"`, positive integer paise, and cannot exceed `refund_due_paise - refunded_paise`. Reaching the full refund amount transitions `payment_status -> "REFUNDED"`.
- **How you confirmed your understanding:**
  - Traced data definitions in `models.py` and `fixtures.py`.
  - Cross-referenced test requirements in `tests/test_acceptance_matrix.py` and `tests/test_contract.py`.
  - Verified against edge cases documented in `data/records.json`.

## 3. Investigation and implementation strategy
- **Issue 1: Event Replay Idempotency Missing**
  - *Symptom:* `test_payment_event_replay_idempotent` and `test_duplicate_event_is_idempotent` failed (`AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']`).
  - *Hypothesis:* Starter code unconditionally appended `event_id` to `processed_event_ids` without checking if `event_id` had already been processed.
  - *Evidence:* Lines 16-44 of starter `service.py` lacked an idempotency guard.
  - *Fix:* Added an idempotency check at the top of `apply_order_event`: if `event_id is not None and event_id in out["processed_event_ids"]`, return `out` immediately without re-executing state mutations or appending duplicate IDs.
- **Issue 2: Unchecked Refund Eligibility and Amount Validation**
  - *Symptom:* Negative amounts, zero, booleans, floats, over-refunds, and refunds on unpaid/active orders were processed.
  - *Hypothesis:* Starter `service.py` added `event.get("amount_paise", 0)` directly to `out["refunded_paise"]` without checking order eligibility, data type, positivity, or remaining balance.
  - *Evidence:* Tests `test_invalid_refund_amounts_are_ignored`, `test_refund_eligibility_matrix`, and `test_refunds_cannot_exceed_due` all failed.
  - *Fix:* Enforced strict validation: `type(amount) is int and amount > 0`, `out.get("status") in ("REJECTED", "CANCELLED")`, `out.get("payment_status") == "PAID"`, `out.get("refund_due_paise", 0) > 0`, and `current + amount <= due`. Updated `payment_status = "REFUNDED"` only when `out["refunded_paise"] == due`.
- **Issue 3: Reconciliation Defect and Key Inconsistency**
  - *Symptom:* Status mismatches were categorized as matched; internal orders using `total_paise` triggered false amount mismatches against provider `amount_paise`.
  - *Hypothesis:* Starter `reconcile_orders` checked `a.get("amount_paise") != b.get("amount_paise")` and placed everything else in `report["matched"]`, completely ignoring status differences. It also failed to fallback to `total_paise` for internal records.
  - *Evidence:* `test_reconciliation_status_mismatch_matrix` failed on status mismatches; demo output had empty `status_mismatches` and false `amount_mismatches`.
  - *Fix:* Implemented `_get_amount(rec)` checking `amount_paise` with fallback to `total_paise`. Computed `amount_diff` and `status_diff` independently. Added to `amount_mismatches` if `amount_diff`, added to `status_mismatches` if `status_diff`, and added to `matched` only when neither differed.

## 4. Implementation decisions
- **Main changes and why:**
  - Modified `service.py`:
    - Added input type validation (`isinstance(order, dict)` and `isinstance(event, dict)`).
    - Early return on duplicate `event_id` in `processed_event_ids`.
    - Handled late `payment_confirmed` for already rejected or cancelled orders by populating `refund_due_paise`.
    - Guarded `refund_processed` with strict eligibility and arithmetic bounds check.
    - Rewrote `reconcile_orders` to check both amount (supporting `total_paise` / `amount_paise`) and status differences deterministically.
- **Alternatives considered and why rejected:**
  - *Allowing `isinstance(amount, int)` without `type(amount) is int`:* In Python, `isinstance(True, int)` evaluates to `True`. Using `isinstance` alone would treat boolean flags as integer paise amounts (1 and 0), failing `test_invalid_refund_amounts_are_ignored[True]`. Strict type checking `type(amount) is int` was required.
  - *Setting payment status to REFUNDED whenever `refunded_paise >= refund_due_paise`:* Rejected because refunds should never exceed the amount due in the first place, and partial refunds must keep the status as `PAID`.
- **Assumptions:**
  - All monetary values are integer paise.
  - Event replay with the same `event_id` is idempotent and safe to discard.
  - Cancellations requested after dispatch started (`OUT_FOR_DELIVERY` or `DELIVERED`) must have no effect on order status.

## 5. Verification
- **Tests added or changed:**
  - Added 8 new regression test suites in `tests/test_contract.py`:
    - `test_late_payment_confirmed_on_rejected_order`
    - `test_late_payment_confirmed_on_cancelled_order`
    - `test_reconcile_both_amount_and_status_mismatch`
    - `test_reconcile_supports_total_paise_internal_orders`
    - `test_refund_boolean_type_ignored`
    - `test_two_step_partial_refund_to_full_refund`
    - `test_replayed_refund_event_does_not_double_refund`
    - `test_malformed_event_and_order_inputs`
- **Commands run and actual results:**
  - `python -m pytest -v`: 220 passed in 0.42s (0 failures, 100% pass rate).
  - `python -m main`:
    ```text
    matched: ['ORD-101']
    missing_from_provider: ['ORD-103']
    missing_from_internal: ['ORD-104']
    amount_mismatches: []
    status_mismatches: ['ORD-102']
    ```
- **Edge cases verified:**
  - Replay of event with duplicate `event_id`.
  - Non-integer / negative / boolean / excessive refund amounts.
  - Order refund attempted on UNPAID or non-terminal states.
  - Order with both amount mismatch and status mismatch simultaneously.
  - Late payment after order rejection/cancellation.
- **Remaining failures or known limitations:**
  - None. All 220 tests pass cleanly without skipping or weakening any checks.
