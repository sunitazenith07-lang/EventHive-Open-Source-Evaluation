# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour
What specific state transition, test failure, data condition, or code path was difficult to understand?

Two specific challenges required careful investigation:
1. **Python Boolean Subtyping Quirk in Financial Validation:** In Python, the `bool` type is a subclass of `int` (`issubclass(bool, int) is True`). When testing `test_invalid_refund_amounts_are_ignored[True]`, a standard type-guard like `isinstance(amount, int) and amount > 0` treats `True` as `1` (1 paise) and attempts to process a 1-paise refund.
2. **Schema Inconsistency in Reconciliation (`total_paise` vs `amount_paise`):** In `fixtures.py`, `sample_orders()` generates internal orders using `new_order()`, which stores the monetary value in `total_paise`. However, `sample_provider_orders()` uses the key `amount_paise`. The original `reconcile_orders()` function exclusively queried `a.get("amount_paise")`, which evaluated to `None`, falsely classifying matching orders (`ORD-101`) as amount mismatches in `python -m main`.

## 2. Evidence
Summarize the relevant assertion, error message, output, or minimal reproducible example. Do not include secrets or real customer data.

1. **Boolean coercion failure:**
   ```python
   amount = True
   isinstance(amount, int) # Returns True!
   # Causes test failure:
   # E AssertionError: assert 1 == 0
   # E where 1 = apply_order_event(order, ev("R", "refund_processed", amount_paise=True))["refunded_paise"]
   ```
2. **Initial demo output contradiction:**
   ```
   matched: []
   amount_mismatches: ['ORD-101', 'ORD-102']
   status_mismatches: []
   ```
   For `ORD-101`, internal had `total_paise=45900`, `status='PLACED'`. Provider had `amount_paise=45900`, `status='PLACED'`. Both amount and status actually matched, but the demo reported it as an amount mismatch.

## 3. What I tried
List the debugging steps or experiments you actually performed and what each one showed.

1. For the boolean issue:
   - *Attempt 1:* Tested `type(amount) is int`. This rejected `True` and `False`, but could fail if a custom `int` subclass was used.
   - *Attempt 2:* Tested `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`. This is the Pythonic standard for numeric guards, ensuring strict exclusion of booleans while accepting standard integers.
2. For the reconciliation schema mismatch:
   - Investigated `fixtures.py` and `data/records.json`. Noticed internal orders in `records.json` and `models.py` use `total_paise`, while provider records use `amount_paise`. Tests in `test_acceptance_matrix.py` also passed internal dicts with `amount_paise`.
   - Tested unified fallback key access: `a.get("amount_paise") if a.get("amount_paise") is not None else a.get("total_paise")`.

## 4. Resolution
What was the root cause? What did you change, and why did that address the cause rather than hide the symptom?

1. **Boolean Resolution:** The root cause was relying on loose type coercion. We updated `apply_order_event` to explicitly verify `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`. This stops any boolean value from being interpreted as a numerical currency amount.
2. **Reconciliation Resolution:** The root cause was an unhandled schema duality between internal order representations (which track `total_paise`) and provider settlement reports (which track `amount_paise`). By resolving either key gracefully on both internal and provider sides, the reconciliation engine correctly identifies true amount matches regardless of dictionary key naming convention. Furthermore, status equality was explicitly added, and orders failing both amount and status are now included in both mismatch categories.

## 5. Proof and regression prevention
Which test(s) demonstrate the fix? What related case could still break?

- **Tests Demonstrating the Fix:**
  - `test_invalid_refund_amounts_are_ignored[True]` and `test_invalid_refund_amounts_are_ignored[False]` in `tests/test_acceptance_matrix.py`.
  - Dedicated regression test `test_boolean_and_type_coercion_safety_in_refunds` in `tests/test_regression_and_edge_cases.py`.
  - `test_reconciliation_supports_both_total_paise_and_amount_paise` and `test_reconciliation_simultaneous_amount_and_status_mismatch`.
- **What could still break:**
  If an upstream caller passes an exotic custom numeric class that does not subclass `int` (e.g. `decimal.Decimal` or `fractions.Fraction`), it would currently be ignored. The specification states all currency must be integer paise, so restricting to native `int` is the intended behavior.

## 6. Unresolved challenge or next step
State any remaining limitation and how you would investigate it next.

- **Reconciliation Cardinality:** Currently, `reconcile_orders` assumes unique `order_id` values per side. If a provider report contains duplicate settlement entries for the same `order_id` (e.g. a charge followed by a refund transaction), dictionary comprehension `right = {r.get("order_id"): r for r in provider}` overwrites earlier entries. A next step would be grouping provider records into a list per `order_id` to aggregate net transaction amounts before comparison.
