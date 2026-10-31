# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The most confusing bug I ran into was during refund amount validation. When I first added a check to ensure refund amounts were integers (`isinstance(amount, int)`), the test `test_invalid_refund_amounts_are_ignored[True]` still failed. 

The test passed a boolean `True` as `amount_paise`. I expected `isinstance(True, int)` to be `False` because a boolean is not a number. But in Python, `bool` is actually a subclass of `int` (`issubclass(bool, int) == True`), and Python treats `True` as `1`. As a result, my check allowed `True` through and refunded 1 paise to the order instead of ignoring it.

A second tricky challenge was handling out-of-order events. If a restaurant rejected an order before the payment gateway webhook arrived, `refund_due_paise` stayed 0 because the payment status was still `UNPAID`. When `payment_confirmed` arrived a few seconds later, the starter code only updated `payment_status = "PAID"`, leaving `refund_due_paise = 0`. The customer had paid, the order was rejected, but they could never get a refund.

## 2. Evidence
1. **The Boolean Subclass Failure:**
   Running `pytest tests/test_acceptance_matrix.py -k "test_invalid_refund_amounts_are_ignored"` gave:
   ```text
   FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True] - AssertionError: assert 1 == 0
   ```
   Checking in the Python REPL confirmed the weird behavior:
   ```python
   >>> isinstance(True, int)
   True
   >>> True == 1
   True
   ```

2. **The Reconciliation Schema Mystery in `main.py`:**
   In the initial demo run, `ORD-101` was marked as an amount mismatch:
   ```text
   amount_mismatches: ['ORD-101', 'ORD-102']
   ```
   Printing both records showed:
   - Internal: `{'order_id': 'ORD-101', 'total_paise': 45900, 'status': 'PLACED', ...}`
   - Provider: `{'order_id': 'ORD-101', 'amount_paise': 45900, 'status': 'PLACED'}`
   The amounts were both 45900, but `service.py` was looking for `a.get("amount_paise")`, which returned `None` for internal orders. So it was comparing `None != 45900`.

## 3. What I tried
1. For the boolean bug, I initially tried checking `if amount:` or `if amount > 0:`. Since `True > 0` is `True` in Python, that still allowed `True` through.
2. I then tested checking the exact type using `type(amount) is int`. That worked because `type(True)` is `bool`, not `int`.
3. To be extra safe and Pythonic, I decided on `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`.
4. For the out-of-order payment issue, I simulated a sequence where `restaurant_rejected` ran first, followed by `payment_confirmed`. I saw that `refund_due_paise` stayed 0. So I updated the `payment_confirmed` handler to check if the order status was already `CANCELLED` or `REJECTED`, and if so, set `refund_due_paise = total_paise`.

## 4. Resolution
- **Root Cause 1 (Refund validation):** The starter code did no type or bounds checking on `amount_paise`. Python's type hierarchy allows `bool` to masquerade as `int`.
  - *Fix:* Explicitly verified that `amount` is an integer and not a boolean, that it is strictly positive, and that it does not exceed the remaining refundable amount (`refund_due_paise - refunded_paise`).
- **Root Cause 2 (Reconciliation keys):** Internal orders created by `models.py` use the key `total_paise`, while external provider records use `amount_paise`.
  - *Fix:* Wrote a helper function `_get_amount(record)` that checks `amount_paise` first, and if not found, falls back to `total_paise`.
- **Root Cause 3 (Out-of-order payments):** Payment webhooks are asynchronous and can arrive after an order is rejected or cancelled.
  - *Fix:* When handling `payment_confirmed`, if the order is already in `CANCELLED` or `REJECTED`, set `refund_due_paise = total_paise`.

## 5. Proof and regression prevention
- **Tests proving the fix:**
  - `test_invalid_refund_amounts_are_ignored[True]` and `test_invalid_refund_amounts_are_ignored[False]` now pass.
  - Added `tests/test_regression_edge_cases.py::test_edge_case_boolean_amount_in_refund_ignored` to ensure neither `True` nor `False` ever alters refund totals.
  - Added `tests/test_regression_edge_cases.py::test_edge_case_late_payment_after_restaurant_rejection` to confirm that late payment confirmation properly sets `refund_due_paise` and allows a subsequent refund.
  - Added `tests/test_regression_edge_cases.py::test_edge_case_reconcile_simultaneous_amount_and_status_mismatch` to verify reconciliation when both fields differ.

## 6. Unresolved challenge or next step
- **Current limitation:**
  Everything currently runs synchronously in memory. The idempotency check looks up `event_id` in a Python list on the order dictionary (`event_id in out["processed_event_ids"]`).
- **Next step for production:**
  If two payment webhooks arrive at the exact same millisecond across two different backend servers, an in-memory check cannot prevent a race condition. In a production system, I would use a distributed lock (e.g. Redis `SETNX`) keyed by `order_id + event_id` or a database table with a unique constraint on `(order_id, event_id)` to guarantee idempotency at the database level.