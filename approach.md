# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
- Commands run before editing:
  - `python -m pytest -q`
  - `python -m main`
- Initial test result:
  `62 failed, 150 passed in 2.61s` (212 total tests).
- Demo/output observed:
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  `ORD-101` and `ORD-102` showed up under `amount_mismatches` because the demo was comparing `total_paise` against `amount_paise`, and `status_mismatches` was empty because status differences were not checked.

## 2. Codebase understanding
- Important files and functions inspected:
  - `service.py`: `apply_order_event` (event handler) and `reconcile_orders` (reconciliation logic).
  - `models.py`: `new_order` function setting default order fields.
  - `fixtures.py` & `main.py`: sample orders and demo script.
  - `tests/test_acceptance_matrix.py` and `tests/test_contract.py`: test cases for order state transitions, idempotency, refunds, and reconciliation.
- Order lifecycle or data flow traced:
  - An order starts as `PLACED` and `UNPAID`.
  - Payment confirmation sets it to `PAID`.
  - The restaurant can accept (`ACCEPTED`) or reject (`REJECTED`) it. If rejected while paid, `refund_due_paise` is set to `total_paise`.
  - A customer can cancel (`cancel_requested`) only while the order is `PLACED` or `ACCEPTED`. If cancelled after payment, `refund_due_paise` is set to `total_paise`.
  - Once dispatch starts (`OUT_FOR_DELIVERY`), cancel requests are ignored.
  - `refund_processed` applies only to paid cancelled/rejected orders, in positive integer paise, up to the remaining due balance.
- How you confirmed your understanding:
  - Traced failing test cases in `test_acceptance_matrix.py` and checked the requirements in `STUDENT_PROBLEM_STATEMENT.md`.

## 3. Investigation and implementation strategy
- Issue 1: Duplicate events
  - What happened: Replaying an event added duplicate event IDs to `processed_event_ids`.
  - Fix: Added a check at the start of `apply_order_event` to return the order immediately if `event_id` is already in `processed_event_ids`.
- Issue 2: Refund validation
  - What happened: Refunds were being applied to unpaid or active orders, accepting invalid types like booleans and floats, and allowing amounts bigger than what was owed.
  - Fix: Checked that the order is `REJECTED` or `CANCELLED`, `payment_status` is `PAID`, `amount` is an integer (`type(amount) is int and amount > 0`), and `amount <= (refund_due_paise - refunded_paise)`. Updated `payment_status` to `REFUNDED` when the full due amount is paid.
- Issue 3: Reconciliation matching
  - What happened: Status mismatches were being put in `matched`, and `ORD-101` failed to match in `main.py` because internal records use `total_paise` while provider records use `amount_paise`.
  - Fix: Checked both `amount_paise` and `total_paise` keys, and checked amount and status mismatches separately.

## 4. Implementation decisions
- Main changes and why:
  - Used `deepcopy` so the original input order isn't modified.
  - Used `type(amount) is int` so `True` or `False` aren't treated as numbers (since `isinstance(True, int)` is True in Python).
  - Kept `processed_event_ids` as a list to match the tests.
- Alternatives considered and why rejected:
  - Using a set for event IDs: Rejected because tests check the list order.
  - Modifying orders in place: Rejected because `test_input_order_is_not_mutated` requires the original order to stay unchanged.
- Assumptions:
  - Amounts are in integer paise.

## 5. Verification
- Tests added or changed:
  - Kept all original tests.
  - Added 9 regression tests in `tests/test_regression.py`.
- Commands run and actual results:
  - `python -m pytest -q`: 221 passed in 0.59s.
  - `python -m main`: `ORD-101` matched, `ORD-102` shows status mismatch.
- Remaining failures or known limitations:
  - None.