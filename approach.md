# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
- Commands run before editing: `python -m pytest -q`
- Initial test result: 62 failed, 150 passed (212 tests).
- Demo output: not recorded before editing. After the fixes, `python -m main` printed:
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```

## 2. Codebase understanding
- Files inspected: `service.py` (`apply_order_event()`, `reconcile_orders()`), `models.py` (`new_order()`), `fixtures.py`, `main.py`, and the tests in `tests/test_acceptance_matrix.py` and `tests/test_contract.py`.
- Data flow traced:
  - An order has `order_id`, `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise` and `processed_event_ids`.
  - `apply_order_event()` deep-copies the order, applies one event and returns the copy.
  - `reconcile_orders()` matches internal and provider records by `order_id` and puts each order in one report category.
- Confirmed by reading the failing tests, running targeted tests, then running the full suite after each fix.

## 3. Investigation and implementation strategy
- **Issue 1: duplicate events.**
  - Symptom/hypothesis: a replayed event applied twice because event IDs were never checked.
  - Fix: `if event_id in out["processed_event_ids"]: return out`
  - Evidence: `test_payment_event_replay_idempotent`, 20 passed in a targeted run.
- **Issue 2: invalid and excessive refunds.**
  - Symptom/hypothesis: the amount was added without validation. Type and sign checks were not enough; the remaining balance also had to be checked.
  - Fix: require an `int`, not a `bool`, greater than 0, and no more than `refund_due_paise - refunded_paise`.
  - Evidence: `test_invalid_refund_amounts_are_ignored`, `test_refunds_cannot_exceed_due`.
- **Issue 3: refund eligibility.**
  - Symptom/hypothesis: payment status alone is not enough; a paid order can still be delivered or failed.
  - Fix: require `payment_status == "PAID"` and `status in ("REJECTED", "CANCELLED")`.
  - Evidence: `test_refund_eligibility_matrix`, 12 passed in a targeted run.
- **Issue 4: reconciliation status mismatches.**
  - Symptom/hypothesis: only the amount was compared before an order was marked `matched`.
  - Fix: add `elif a.get("status") != b.get("status")` and report it under `status_mismatches`.
  - Evidence: `test_reconciliation_status_mismatch_matrix` and new reconciliation tests.

## 4. Implementation decisions
- Main changes: small conditions inside the existing functions, reusing the existing report categories.
- Alternatives rejected: helper functions or a refactor (not needed for four small checks); reporting both mismatch types for one order (it would put one order in two categories). Nothing was benchmarked.
- Assumptions: event IDs identify events processed once; refund amounts are integer paise; only paid `REJECTED`/`CANCELLED` orders are refundable; reconciliation matches by `order_id`.

## 5. Verification
- Tests added: `tests/test_my_regressions.py` with 14 tests. No existing test file was modified.
- Commands and results:
  - Initial `python -m pytest -q`: 62 failed, 150 passed.
  - Targeted idempotency tests: 20 passed. Refund eligibility matrix: 12 passed.
  - After adding my first 6 tests: 4 failed, 214 passed (wrong event key in my test helper, see `challenges.md`).
  - Final `python -m pytest -q`: 226 passed.
- Edge cases verified: replayed event, invalid and excessive refunds, partial then full refund, ineligible states, cancel after dispatch, reconciliation amount/status cases. See `TESTING.md`.
- Limitations:
  - If both amount and status differ, only the amount mismatch is recorded (`if`/`elif`).
  - An event with no `event_id` is treated as a duplicate of any earlier event with no ID.
  - An ignored refund still records its event ID.
  - The demo has an empty `status_mismatches`, so only the tests exercise that branch.

Record actual engineering decisions and evidence. Do not claim tests or experiments you did not run.