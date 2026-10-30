# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour
During the initial investigation, the most subtle issue occurred in Python's type handling of `isinstance` for numeric validation in refunds, combined with bridging schemas between internal orders (`total_paise`) and provider summaries (`amount_paise`) in reconciliation:
1. In Python, `bool` is a subclass of `int` (`issubclass(bool, int) is True`, where `True == 1` and `False == 0`). A standard check like `isinstance(amount, int) and amount > 0` allowed `amount_paise = True` to pass as a valid 1-paise refund.
2. The offline demo `main.py` initially reported `ORD-101` and `ORD-102` as `amount_mismatches: ['ORD-101', 'ORD-102']`. However, inspecting `fixtures.py` showed `ORD-101` was initialized with `total_paise=45900` internally and `amount_paise=45900` in the provider record, so it should have matched. The starter `reconcile_orders` implementation only read `a.get("amount_paise")`, which evaluated to `None` for internal order objects, causing a false mismatch against `45900`.

## 2. Evidence
1. **Pytest Failure with Boolean Amount:**
   Running `test_invalid_refund_amounts_are_ignored[True]` initially caused:
   ```text
   FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
   AssertionError: assert 1 == 0
   ```
   `True` was evaluated as `1` paise and incremented `refunded_paise` to 1.
2. **Demo Output Mismatch:**
   Running `python -m main` produced:
   ```text
   matched: []
   amount_mismatches: ['ORD-101', 'ORD-102']
   status_mismatches: []
   ```
   `ORD-101` had identical amounts (45900) and statuses (`PLACED`), but was marked as an amount mismatch because `new_order` stores `total_paise` instead of `amount_paise`.

## 3. What I tried
1. For amount validation, I first checked `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`. Then I evaluated whether `type(amount) is int and amount > 0` was cleaner and more idiomatic. Both correctly exclude boolean values and non-integers.
2. For reconciliation, I experimented with modifying `models.new_order` to store both `total_paise` and `amount_paise`. However, changing model defaults risks breaking downstream callers or tests that assert exact order keys. Instead, I adapted `reconcile_orders` to check `r.get("amount_paise") if "amount_paise" in r else r.get("total_paise")`.
3. For status mismatches, I verified how the report should behave when both amount and status mismatch simultaneously (e.g. `amount_paise`: 1000 vs 2000 and status: `PLACED` vs `DELIVERED`). By separating the flags (`amount_mismatch` and `status_mismatch`), the order is correctly placed in both mismatch categories and omitted from `matched`.

## 4. Resolution
1. **Strict Type Checking:** Used `type(amount) is int and amount > 0`. This guarantees that boolean flags (`True`/`False`), floats (`0.5`, `2.2`), strings (`"10"`), None, and negative values are strictly ignored, keeping `refunded_paise` unmodified.
2. **Flexible Amount Key Lookup:** In `reconcile_orders`, extracted amounts dynamically:
   ```python
   a_amount = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
   b_amount = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")
   ```
3. **Independent Mismatch Tracking:** Decoupled amount check from status check:
   ```python
   amount_mismatch = (a_amount != b_amount)
   status_mismatch = (a_status != b_status)

   if amount_mismatch:
       report["amount_mismatches"].append(key)
   if status_mismatch:
       report["status_mismatches"].append(key)
   if not amount_mismatch and not status_mismatch:
       report["matched"].append(key)
   ```

## 5. Proof and regression prevention
1. Added `test_refund_rejects_boolean_amounts` in `tests/test_regression.py` to assert that `True` and `False` leave `refunded_paise == 0`.
2. Added `test_reconciliation_dual_mismatch_amount_and_status` to ensure dual mismatches append to both lists and never to `matched`.
3. All 15 cases of `test_invalid_refund_amounts_are_ignored` and all 7 cases of `test_reconciliation_status_mismatch_matrix` in `tests/test_acceptance_matrix.py` pass without regression.

## 6. Unresolved challenge or next step
In an asynchronous distributed production environment, order events and refund webhooks often arrive out of chronological order (e.g. refund webhook arriving before the cancellation event is processed by the order service). In the current implementation, an early refund for an order still in `PLACED` state is safely ignored; however, a production system would require a retry mechanism, an out-of-order event staging buffer, or a dead-letter queue to replay the refund event once the order transitions to `CANCELLED`.
