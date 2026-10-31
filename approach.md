# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
- Commands run before editing: `python -m pytest -q`
- Original test result before any fix: 62 failed, 150 passed (212 tests total).
- Result at the start of this commit (after the duplicate-event and refund-validation fixes): [FILL IN: full-suite summary line from commit 2]
- Demo/output observed: [FILL IN: output of `python -m main` before this fix, or write "not recorded before this fix"]

## 2. Codebase understanding
- Important files and functions inspected:
  - `service.py`: the `refund_processed` branch of `apply_order_event()`.
  - `models.py`: `new_order()`, which sets the initial order status and payment status `UNPAID`.
  - Relevant tests in `tests/test_acceptance_matrix.py` and `tests/test_contract.py`.
- Order lifecycle or data flow traced:
  - A paid order that is rejected or cancelled gets a refund due equal to its order total.
  - `refund_processed` events then add to `refunded_paise`.
  - Payment status changes to `REFUNDED` when the refunded total reaches the refund due.
- How understanding was confirmed:
  - Inspected the refund branch and the order and payment status values it can see.
  - Read the refund eligibility matrix test to see which order and payment states must allow a refund.
  - Ran the matrix test after each change.

## 3. Investigation and implementation strategy

- Issue 3: Refund eligibility.
  - Symptom: Refunds were being applied to orders that were not eligible.
  - Investigation: Examined `test_refund_eligibility_matrix`, which covers unpaid, delivered, failed, rejected and cancelled orders, among other states. Checking only the payment status left one matrix case failing: an order in `FAILED` state with payment status `PAID` was still treated as eligible.
  - Fix: Add two conditions to the refund check: payment status must be `PAID` and order status must be `REJECTED` or `CANCELLED`:
    ```python
    if (
        isinstance(amount, int)
        and not isinstance(amount, bool)
        and amount > 0
        and amount <= out["refund_due_paise"] - out["refunded_paise"]
        and out["payment_status"] == "PAID"
        and out["status"] in ("REJECTED", "CANCELLED")
    ):
    ```
  - Evidence: The targeted refund eligibility matrix passed 12 cases.

## 4. Implementation decisions
- Main changes and why:
  - Check the payment status as well as the order status, because a refund only makes sense for an order that has actually been paid.
  - Restrict the order status to `REJECTED` or `CANCELLED`, because those are the states that create a refund due.
- Alternatives considered and why rejected:
  - Checking only the payment status was tried first and was not enough (the `FAILED` + `PAID` case).
  - Moving the eligibility rules into a helper function was not chosen; adding conditions to the existing check was enough.
  - No alternative implementation was formally benchmarked.
- Assumptions:
  - Only paid orders in `REJECTED` or `CANCELLED` state are eligible for refund processing.
  - Refund amounts are integer paise.
  - The order status is stored in `out["status"]` and the payment status in `out["payment_status"]`.

## 5. Verification
- Tests added or changed: No test files were modified. Existing tests were used as regression checks.
- Commands run and actual results:
  - Targeted refund eligibility matrix: 12 passed.
  - Full `python -m pytest -q` after this fix: [FILL IN: summary line]
- Edge cases verified: [FILL IN after running; see TESTING.md]
- Remaining failures or known limitations:
  - Reconciliation status mismatch is not fixed at this commit.
  - An ignored (invalid or ineligible) refund event still has its event ID appended to `processed_event_ids` because the append runs for every event. This was read from the code and was not tested.

Record actual engineering decisions and evidence. Do not claim tests or experiments you did not run.