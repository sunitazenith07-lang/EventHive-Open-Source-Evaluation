# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The most subtle challenge was the interaction between Python's type hierarchy for boolean values in refund amount validation and the schema discrepancy between internal orders and provider orders in reconciliation:

1. **Python Boolean as Subclass of `int`:**
   In Python, `bool` is a subclass of `int` (`issubclass(bool, int) == True`). When checking `isinstance(amount, int)`, values like `True` and `False` pass the check. In `test_invalid_refund_amounts_are_ignored[True]`, `True > 0` evaluates to `True` (equivalent to `1`), causing an invalid refund event with `amount_paise=True` to be accepted as a 1-paise refund instead of being rejected.
   
2. **Schema Inconsistency Between Internal and Provider Records:**
   In `main.py` and `fixtures.py`, `sample_orders()` creates orders via `new_order()`, which stores total amounts in `total_paise`. However, provider orders and synthetic test fixtures use `amount_paise`. The starter implementation of `reconcile_orders` exclusively referenced `a.get("amount_paise")`, leading to internal orders reporting `None != 45900`, incorrectly categorizing valid matching orders as `amount_mismatches`. Furthermore, when both amount and status differed, handling them independently without conflating `matched` was critical.

## 2. Evidence
- **Boolean Type Error:**
  Running `test_invalid_refund_amounts_are_ignored[True]` with `isinstance(amount, int)` resulted in:
  ```text
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
  AssertionError: assert 1 == 0
  ```
- **Reconciliation Status Mismatch & Missing Key Error:**
  Running `main.py` produced:
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  Here, `ORD-101` had `total_paise == 45900` matching provider `amount_paise == 45900`, but was reported as an amount mismatch. `ORD-102` had equal amounts (129900) but mismatched statuses (`ACCEPTED` vs `CANCELLED`), yet was absent from `status_mismatches`.

## 3. What I tried
- Tested `isinstance(amount, int) and amount > 0`: Observed that `test_invalid_refund_amounts_are_ignored[True]` failed because `bool` is an instance of `int` and `True > 0` is `1 > 0`.
- Tested `type(amount) is int and amount > 0`: Verified that `type(True) is int` evaluates to `False`, strictly filtering out booleans while allowing genuine integer amounts.
- Tested `a.get("amount_paise") != b.get("amount_paise")`: Discovered that internal records created by `new_order()` store `total_paise`, causing `None != 45900`.
- Tested helper `_get_amount(rec)` checking `rec.get("amount_paise") if "amount_paise" in rec and rec["amount_paise"] is not None else rec.get("total_paise")`: Verified that both internal and provider amount representations are normalized accurately.

## 4. Resolution
- **Type Checking:** Replaced generic `isinstance(amount, int)` with `type(amount) is int`, ensuring only actual `int` instances are processed for refunds.
- **Unified Amount Extractor:** Implemented `_get_amount()` in `reconcile_orders` to check `amount_paise` first and fall back to `total_paise`.
- **Decoupled Reconciliation Reporting:** Evaluated `amount_diff` and `status_diff` independently. If amounts differ, append to `amount_mismatches`. If statuses differ, append to `status_mismatches`. Append to `matched` only when neither differs.
- **Late Payment Handling:** Added state logic to `payment_confirmed` such that if an order had already been rejected or cancelled while unpaid, arriving payment marks it as `PAID` and sets `refund_due_paise = total_paise` to prevent trapped customer funds.

## 5. Proof and regression prevention
- **Protected Tests in Acceptance Suite:**
  - `test_invalid_refund_amounts_are_ignored` (15 parameterized edge-case amounts including `True`, `False`, floats, and negatives).
  - `test_reconciliation_status_mismatch_matrix` (12 status pair scenarios).
- **Added Regression Tests in `test_contract.py`:**
  - `test_refund_boolean_type_ignored`
  - `test_reconcile_supports_total_paise_internal_orders`
  - `test_reconcile_both_amount_and_status_mismatch`
  - `test_late_payment_confirmed_on_rejected_order`
- **Related Cases Protected:**
  - Attempting to replay an event with the same ID cannot alter state twice or double-refund.

## 6. Unresolved challenge or next step
- In this offline simulation, records are in-memory dictionaries. In a distributed production system:
  - Event processing should utilize atomic idempotency storage (e.g. database unique constraint or transactional outbox pattern) rather than in-memory list searching.
  - Reconciliation across massive datasets would benefit from streaming or chunked cursors rather than in-memory set unions.
