# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour
- What specific state transition, test failure, data condition, or code path was difficult to understand?
Two notable challenges required careful investigation:
1. **Python Boolean Type Inheritance in Integer Validation**: During refund amount validation, parameterized tests in `tests/test_acceptance_matrix.py` tested inputs such as `True` and `False`. Initially using `isinstance(amount, int)` allowed `True` (treated numerically as `1`) to pass validation and apply a 1 paise refund, causing `test_invalid_refund_amounts_are_ignored[True]` to fail.
2. **Dual-Mismatch Reconciliation Reporting**: When reconciling orders between internal records and payment provider summaries, orders could have both an amount discrepancy and a lifecycle status discrepancy simultaneously. In naive if-elif branching, flagging an amount mismatch would bypass status comparison, causing status mismatches to be omitted.
3. **Data Model Field Asymmetry**: Synthetic internal orders defined in `models.py` (`new_order`) and `fixtures.py` store order amounts under `total_paise`, while external payment provider records use `amount_paise`. An exact key lookup `a.get("amount_paise")` on internal orders returned `None`, triggering false-positive amount mismatches even when totals matched.

## 2. Evidence
- Summarize the relevant assertion, error message, output, or minimal reproducible example. Do not include secrets or real customer data.
- **Boolean type leakage assertion failure**:
  ```
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
  AssertionError: assert 1 == 0
  where 1 = result['refunded_paise']
  ```
- **Reconciliation demo symptom**:
  Running `python -m main` on untouched code reported:
  `amount_mismatches: ['ORD-101', 'ORD-102']`
  `ORD-101` had 45900 paise internally and 45900 paise with the provider, yet was reported as mismatched because `total_paise` was not checked.
- **Status mismatch masking**:
  In `service.py`, `report["matched"].append(key)` was executed under `else:` after amount comparison, failing `test_reconcile_reports_status_difference`:
  ```
  FAILED tests/test_contract.py::test_reconcile_reports_status_difference
  AssertionError: assert [] == ['A']
  ```

## 3. What I tried
- List the debugging steps or experiments you actually performed and what each one showed.
1. **For Integer Validation**:
   - First experimented with `isinstance(amount, int) and amount > 0`. This failed for `True` because `bool` is a subclass of `int` in Python (`issubclass(bool, int) is True`).
   - Evaluated `type(amount) is int and amount > 0`. Testing in Python REPL confirmed: `type(True) is int` evaluates to `False`, while `type(100) is int` evaluates to `True`.
2. **For Reconciliation Dual Mismatches**:
   - Analyzed whether an order with both amount and status differences should be in `amount_mismatches`, `status_mismatches`, or both. Requirement 6 states: "Report missing records, amount mismatches and status mismatches separately and deterministically."
   - Replaced mutual-exclusion (`if / elif`) with independent evaluation flags: `has_amount_diff` and `has_status_diff`.
3. **For Field Asymmetry**:
   - Built `_extract_amount(record)` helper to check `amount_paise` first, then fall back to `total_paise`.

## 4. Resolution
- What was the root cause? What did you change, and why did that address the cause rather than hide the symptom?
- Used strict type equivalence: `type(amount) is int and amount > 0`. This cleanly rejects booleans, floats (`0.5`), strings (`"10"`), and nested collections without extra type casting.
- Refactored `reconcile_orders`:
  - Defined `has_amount_diff = (amount_a != amount_b)` and `has_status_diff = (status_a != status_b)`.
  - Added the order ID to `amount_mismatches` if `has_amount_diff` is true.
  - Added the order ID to `status_mismatches` if `has_status_diff` is true.
  - Only added to `matched` if neither mismatch occurred (`not has_amount_diff and not has_status_diff`).
  - Sorted the composite keys with `sorted(set(left) | set(right), key=lambda x: str(x))` to guarantee deterministic report outputs.

## 5. Proof and regression prevention
- Which test(s) demonstrate the fix? What related case could still break?
- The fix resolved all 62 initial test failures in `test_contract.py` and `test_acceptance_matrix.py`.
- Added dedicated regression tests in `tests/test_regression.py`:
  - `test_boolean_refund_amount_rejected`: specifically asserts that `amount_paise=True` and `amount_paise=False` are rejected with `refunded_paise == 0`.
  - `test_reconciliation_simultaneous_amount_and_status_mismatch`: verifies that an order differing in both amount and status is added to both mismatch reports simultaneously.
  - `test_reconciliation_uses_internal_total_paise`: verifies seamless reconciliation between internal records (`total_paise`) and provider records (`amount_paise`).

## 6. Unresolved challenge or next step
- State any remaining limitation and how you would investigate it next.

- If you did not encounter a major blocker, say that clearly and describe the hardest edge case you deliberately tested and what it taught you. Do not manufacture a story; describe observable engineering work.

- In high-throughput distributed systems, in-memory deduplication via `processed_event_ids` list lookup is $O(N)$ per event. In a production database or key-value store, this should be backed by an idempotent unique index on `(order_id, event_id)` or a Redis set with TTL.
- If currency multi-denomination (e.g. fractional paise or multi-currency conversions) were introduced, fixed-point integer arithmetic or `decimal.Decimal` would be needed to prevent floating-point inaccuracies.