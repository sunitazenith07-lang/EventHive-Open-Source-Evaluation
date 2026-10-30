# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour
Two subtle issues caused the most confusion during debugging:
1. Python's boolean type inheritance: In Python, `bool` is a subclass of `int`. As a result, writing `isinstance(amount, int)` allows `True` and `False` to pass validation, where `True` evaluates numerically to `1`. In `test_invalid_refund_amounts_are_ignored[True]`, `amount_paise=True` was treated as 1 paise, causing a test failure.
2. Asymmetric amount keys across datasets: In `models.py` and `fixtures.py`, internal order dictionaries store the amount under `total_paise`, whereas provider records and some test dictionaries store it under `amount_paise`. In the starter offline demo (`main.py`), looking up `a.get("amount_paise")` returned `None` for internal orders, incorrectly flagging perfectly matching orders like `ORD-101` as amount mismatches (`None != 45900`).

## 2. Evidence
- For the boolean type pitfall:
  ```text
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
  assert 1 == 0
  ```
- For the asymmetric dictionary key issue:
  Running `python -m main` on the starter code produced:
  ```text
  matched: []
  amount_mismatches: ['ORD-101', 'ORD-102']
  ```
  Inspecting `sample_orders()` showed:
  `{"order_id": "ORD-101", "total_paise": 45900, "status": "PLACED"}` (has `total_paise`)
  While `sample_provider_orders()` had:
  `{"order_id": "ORD-101", "amount_paise": 45900, "status": "PLACED"}` (has `amount_paise`)

## 3. What I tried
- For the type check:
  - First attempt: Tried `if isinstance(amount, int):` which caused `test_invalid_refund_amounts_are_ignored[True]` to fail because `isinstance(True, int)` is `True`.
  - Second attempt: Tried `if isinstance(amount, int) and not isinstance(amount, bool):`. This succeeded.
  - Final refinement: Replaced with the more direct and idiomatic `type(amount) is int and amount > 0`, which cleanly excludes subclasses like `bool` without extra isinstance calls.
- For the schema difference in reconciliation:
  - Traced `reconcile_orders` line-by-line comparing `left` and `right`.
  - Confirmed that internal orders can use `total_paise` (from `models.new_order`) or `amount_paise` (from unit test summaries).
  - Implemented fallbacks:
    `a_amount = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")`
    `b_amount = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")`

## 4. Resolution
- Fixed `apply_order_event` to use `type(amount) is int and amount > 0` and enforce bounds `amount <= (due - already_refunded)`.
- Fixed `reconcile_orders` to resolve amounts using either key (`amount_paise` or `total_paise`), compare statuses independently, and assign mismatches to `amount_mismatches` and/or `status_mismatches` while reserving `matched` strictly for orders with identical amounts and statuses.

## 5. Proof and regression prevention
- The resolution was verified by running the entire pytest suite:
  - All 212 original tests pass.
  - Added `tests/test_regression.py::test_boolean_refund_amount_rejected` and `test_reconcile_handles_total_paise_and_amount_paise_keys` to ensure these regressions cannot recur.
  - Running `python -m main` now correctly reports `ORD-101` in `matched` and `ORD-102` in `status_mismatches`.

## 6. Unresolved challenge or next step
- In an asynchronous distributed system, event arrival order is not guaranteed. For example, if a `refund_processed` event arrives before a delayed `restaurant_rejected` event, the refund is currently dropped because the order is not yet marked `REJECTED`.
- As a next step, an event buffering or out-of-order event staging queue could be added to hold premature events until prerequisite status transitions are applied.