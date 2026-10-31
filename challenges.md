# challenges.md - COMPULSORY Submission

## 1. Challenge or confusing behaviour
Two subtle challenges arose during investigation:
1. **The Python Boolean Subclass Trap in Amount Validation**:
   When testing invalid refund amounts (`test_invalid_refund_amounts_are_ignored`), parameterized values included `True` and `False`. Initially using `isinstance(amount, int)` allowed `True` to pass as `1` paise because in Python `bool` inherits from `int` (`issubclass(bool, int) is True`).
2. **Dual-Key Amount Discrepancy Across Datasets**:
   Running `python -m main` showed `amount_mismatches: ['ORD-101', 'ORD-102']` even though `ORD-101` had matching amounts in `sample_orders()` (45900) and `sample_provider_orders()` (45900). Tracing revealed that internal orders created by `models.new_order` use `total_paise`, whereas provider records use `amount_paise`. The starter `reconcile_orders` evaluated `a.get("amount_paise") != b.get("amount_paise")`, which evaluated `None != 45900`.
3. **Late-Arriving Payment Confirmations**:
   When an order is cancelled or rejected prior to payment confirmation, its `payment_status` is `UNPAID` and `refund_due_paise` remains `0`. If `payment_confirmed` arrives out of order after the cancellation or rejection, leaving `refund_due_paise` at `0` prevents valid refund processing.

## 2. Evidence
- **Boolean amount assertion error**:
  ```text
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
  AssertionError: assert 1 == 0
  ```
- **Demo output mismatch in `main.py`**:
  ```text
  matched: []
  amount_mismatches: ['ORD-101', 'ORD-102']
  ```
  Expected `ORD-101` to be `matched` because both sides represent an order of 45,900 paise in `PLACED` status.
- **Late payment test scenario**:
  An order in `CANCELLED` status with `UNPAID` receives `payment_confirmed`. If `refund_due_paise` is not updated to `total_paise`, subsequent `refund_processed` attempts fail because remaining refundable balance evaluates to `0 - 0 = 0`.

## 3. What I tried
1. For amount validation, tested `isinstance(amount, int) and not isinstance(amount, bool)` versus `type(amount) is int`. Using exact type check `type(amount) is int` was cleaner, more idiomatic, and rejected both `True` and `False` cleanly while accepting standard integer paise.
2. For reconciliation amount extraction, tested:
   - `record.get("amount_paise") or record.get("total_paise")`: Failed when `amount_paise` was `0`, as `0` is falsy and fell back to `total_paise`.
   - Dedicated extractor function:
     ```python
     def _get_amount(record: dict):
         if "amount_paise" in record and record["amount_paise"] is not None:
             return record["amount_paise"]
         return record.get("total_paise")
     ```
     This correctly preserved explicit `0` values and properly resolved `total_paise` for internal order models.
3. For late payments, tested updating `refund_due_paise` on `payment_confirmed` when `status in ("REJECTED", "CANCELLED")`. Verified with a new regression test that this maintains financial consistency.

## 4. Resolution
- **Type Checking**: Replaced loose checks with `type(amount) is int and amount > 0`.
- **Key Normalization**: Created `_get_amount(record)` in `reconcile_orders` to bridge internal `total_paise` and external `amount_paise` schemas.
- **Status Reconciliation**: Added separate checks for `has_amount_mismatch` and `has_status_mismatch`. Only orders where neither mismatch exists are added to `matched`.
- **Late Payment Handling**: In `apply_order_event`, when `kind == "payment_confirmed"`, if `status in ("REJECTED", "CANCELLED")` and `refund_due_paise == 0`, initialize `refund_due_paise = out.get("total_paise", 0)`.

## 5. Proof and regression prevention
- Acceptance tests:
  - `test_invalid_refund_amounts_are_ignored[True]` and `[False]` now pass.
  - `test_reconciliation_status_mismatch_matrix` passes across all 12 status pairs.
- Added regression tests in `tests/test_regression.py`:
  - `test_refund_rejection_for_boolean_amount`
  - `test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due`
  - `test_reconciliation_with_total_paise_and_malformed_entries`
- All 220 tests pass in CI and local test runs.

## 6. Unresolved challenge or next step
- **Event Ordering and Race Conditions**: In a distributed deployment, events could arrive out of order (e.g., refund before payment confirmation). The current implementation handles late payment confirmation after rejection/cancellation, but a refund arriving *before* payment confirmation is rejected as unpaid. In production, a pending event queue or state machine with event re-sequencing would be recommended.
