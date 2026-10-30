# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
Two things tripped me up while fixing the tests:
1. When validating refund amounts with `isinstance(amount, int)`, the test passing `amount_paise=True` still failed. I forgot that in Python, `bool` is a subclass of `int`, so `True` was treated as `1` paise.
2. When running `python -m main`, `ORD-101` was showing up in `amount_mismatches` even though both sides had `45900`. Looking closer at `models.py` vs `fixtures.py`, I realized internal orders use the key `total_paise` while provider records use `amount_paise`.

## 2. Evidence
- **Boolean test failure:**
  `FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True] - AssertionError: assert 1 == 0`
- **Main demo output before fix:**
  `amount_mismatches: ['ORD-101', 'ORD-102']` and `matched: []`, because `a.get("amount_paise")` was returning `None` for internal orders created by `new_order()`.

## 3. What I tried
- First, I used `isinstance(amount, int) and amount > 0` for refund amounts, which fixed strings, floats, and `None`, but `True` still passed because `True > 0` is true in Python.
- Then I added `and not isinstance(amount, bool)` to specifically block booleans.
- For reconciliation, I first tried `a.get("amount_paise") or a.get("total_paise")`, but realized that if an order had an amount of `0`, `0` is falsy in Python and could cause bugs. So I switched to `"amount_paise" in a`.

## 4. Resolution
- In `apply_order_event`, I checked `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`.
- In `reconcile_orders`, I grabbed the amount using:
  `a_amt = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")`
  and checked `amount_match` and `status_match` separately so an order can be flagged for either or both.

## 5. Proof and regression prevention
- `test_invalid_refund_amounts_are_ignored` now passes for all 15 invalid inputs including `True` and `False`.
- Added `test_reconcile_orders_supports_both_key_conventions` and `test_reconcile_orders_handles_simultaneous_amount_and_status_mismatch` in `tests/test_regression.py`.

## 6. Unresolved challenge or next step
- Everything works for single-threaded in-memory dicts, but if two refund events arrived at the exact same time in a real server, they could both pass the `amount <= remaining_due` check before updating the database. Next step in a real app would be using database transactions or row locks.
