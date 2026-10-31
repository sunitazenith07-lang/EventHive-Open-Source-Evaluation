# approach.md - Required submission

## 1. Baseline

- Commands run before editing: `python -m pytest -q`
- Initial test result: 189 passed, 23 failed.
- Demo/output observed: Ran `python -m main`. The output showed missing orders, amount mismatches, and a status mismatch.

## 2. Codebase understanding

- Important files and functions inspected: `service.py`, `main.py`, and the relevant tests in the `tests/` directory.
- Important functions: `apply_order_event()` and `reconcile_orders()`.
- Order lifecycle or data flow traced: Order events are processed by `apply_order_event()`, which returns an updated order. Transaction summaries are compared by `reconcile_orders()`.
- How understanding was confirmed: By running the visible pytest suite and the offline demo and examining their outputs.

## 3. Investigation and implementation strategy

### Issue 1: Partial refund status

- Observed symptom: Tests expected the payment status to remain `PAID` after a partial refund, but the implementation returned `PARTIALLY_REFUNDED`.
- Hypothesis: The partial refund branch was changing the payment status earlier than the expected contract allowed.
- Evidence: `test_partial_refund_is_not_marked_complete` failed.
- Fix chosen: Keep the payment status as `PAID` after a partial refund and change it to `REFUNDED` only when the full refund amount has been processed.

### Issue 2: Multiple refund events

- Observed symptom: A second valid refund event was not added to the previously refunded amount.
- Hypothesis: The eligibility condition rejected the next refund because the payment status had changed after the first partial refund.
- Evidence: The parametrized `test_refunds_cannot_exceed_due` tests failed.
- Fix chosen: Keep the payment status as `PAID` until the full refund is completed, allowing subsequent valid refund events to be processed while preventing the refunded amount from exceeding the due amount.

### Issue 3

- No third defect documented.

## 4. Implementation decisions

- Main changes and why: Updated the refund-processing logic in `service.py` so partial refunds keep the status as `PAID` and a full refund changes it to `REFUNDED`.
- Alternatives considered and why rejected: Marking a partial refund as `PARTIALLY_REFUNDED` was rejected because the visible tests expected `PAID` until the full refund was complete.
- Assumptions: The visible test contract defines the expected payment status and refund accumulation behaviour.

## 5. Verification

- Tests added or changed: No tests were added or changed during the fix.
- Commands run and actual results:
  - `python -m pytest -q` — final result: **212 passed in 0.26s**.
  - `python -m main` — completed successfully and printed the reconciliation report.
- Edge cases verified: Partial refunds, full refunds, multiple refund events, and attempts to refund beyond the amount due, as covered by the visible tests.
- Remaining failures or known limitations: No failures in the visible test suite. Additional hidden tests and submission requirements have not yet been verified.