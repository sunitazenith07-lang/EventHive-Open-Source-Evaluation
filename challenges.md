# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour
The trickiest bug was with boolean amounts in refunds. In `test_invalid_refund_amounts_are_ignored`, one of the inputs was `amount_paise=True`. I initially used `isinstance(amount, int)`, but the test still failed because in Python, `bool` is a subclass of `int`, so `isinstance(True, int)` is True and `True` gets treated as `1`.

Another issue was in `reconcile_orders`. When running `python -m main`, `ORD-101` showed up as an amount mismatch even though both sides had 45900. Looking at `models.py` and `fixtures.py`, I realized internal orders use the key `total_paise` while provider records use `amount_paise`. The code was doing `a.get("amount_paise")`, which returned `None` for the internal order.

## 2. Evidence
- Test failure with `True`:
  ```text
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
  assert 1 == 0
  ```
- Demo output before fix:
  ```text
  amount_mismatches: ['ORD-101', 'ORD-102']
  ```
  Internal had `{"total_paise": 45900}` and provider had `{"amount_paise": 45900}`.

## 3. What I tried
- For the boolean bug, I first tried `isinstance(amount, int) and not isinstance(amount, bool)`. That passed, but using `type(amount) is int` was simpler because `type(True)` is `bool`, not `int`.
- For the dictionary key issue, I changed the lookup to check for `amount_paise` first, and if not present, check `total_paise`.

## 4. Resolution
- Used `type(amount) is int and amount > 0 and amount <= remaining_due` to validate refund amounts.
- Updated `reconcile_orders` to handle both `amount_paise` and `total_paise`, and added separate checks for amount and status mismatches.

## 5. Proof and regression prevention
- All 212 starter tests passed.
- Added tests in `tests/test_regression.py` for boolean refund values (`test_boolean_refund_amount_rejected`) and key normalization (`test_reconcile_handles_total_paise_and_amount_paise_keys`).
- `python -m main` now correctly matches `ORD-101`.

## 6. Unresolved challenge or next step
- If events arrive out of order (for example, a refund arriving before the cancellation event), the refund gets dropped because the order is not yet marked cancelled. In a real system, you would hold or retry out-of-order events.