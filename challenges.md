# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The most subtle challenge encountered was Python's type hierarchy regarding booleans in `refund_processed` events. Specifically, `test_invalid_refund_amounts_are_ignored` tests passing `True` as an `amount_paise`. In Python, `isinstance(True, int)` evaluates to `True` because `bool` is a subclass of `int`. Without an explicit check, `amount_paise=True` would process as a `1` paise refund, failing the test.

Another tricky behavior was dictionary key differences between internal orders (`total_paise`) and provider records (`amount_paise`) in reconciliation.

## 2. Evidence
Running `pytest` against an initial type-check `isinstance(amount, int) and amount > 0` caused:
```text
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
AssertionError: assert 1 == 0
```
And in reconciliation, the baseline demo failed to match `ORD-101` even though both sides represented a 45,900 paise order, because `a.get("amount_paise")` returned `None`.

## 3. What I tried
1. First verified how Python evaluates `isinstance(True, int)` using `python -c "print(isinstance(True, int))"` (output: `True`).
2. Tested `type(amount) is int` vs `isinstance(amount, int) and not isinstance(amount, bool)`.
3. Verified the internal dictionary schema in `models.py` to confirm that `new_order` creates `total_paise`, whereas external providers report `amount_paise`.

## 4. Resolution
1. Strengthened type validation to:
   ```python
   isinstance(amount, int) and not isinstance(amount, bool) and amount > 0
   ```
   This cleanly rejects booleans while accepting all valid integers.
2. In `reconcile_orders`, normalized amount extraction:
   ```python
   a_amt = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
   ```
   This handles both internal orders and standalone provider summaries.

## 5. Proof and regression prevention
- Regression test added: `test_regression_boolean_refund_is_rejected` explicitly passes `amount_paise=True` and asserts `refunded_paise == 0`.
- Matrix test: `test_invalid_refund_amounts_are_ignored` now passes across all 15 edge values (including `True`, `False`, floats, and bounds).

## 6. Unresolved challenge or next step
Currently, event processing operates in-memory on individual dictionaries. In a production distributed setting, event idempotency would require an external distributed lock or transactional datastore to prevent race conditions during concurrent webhook delivery.
