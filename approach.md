# approach.md - Required submission

## 1. Baseline
- Commands run before editing: 
  - `python3 -m pip install -r requirements-dev.txt`
  - `python3 -m pytest -q`
  - `python3 -m main`
- Initial test result: FAILED: 62, PASSED: 150 (Total: 212 tests)
- Demo/output observed when running `python3 -m main`:
  - `matched: []`
  - `missing_from_provider: ['ORD-103']`
  - `missing_from_internal: ['ORD-104']`
  - `amount_mismatches: ['ORD-101', 'ORD-102']`
  - `status_mismatches: []`

## 2. Codebase understanding
- Important files and functions inspected: `service.py` (`apply_order_event`, `reconcile_orders`), `models.py`, and test files under `tests/`.
- Order lifecycle traced: From `PLACED` -> `ACCEPTED`/`REJECTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`, or `CANCELLED` at valid points.
- How you confirmed your understanding: Ran the initial pytest suite to see exactly which test cases failed and why.

## 3. Investigation and implementation strategy
- Issue 1 (State Transitions): Cancel requests after dispatch were incorrectly allowed or not validated properly. Fixed by locking states once `OUT_FOR_DELIVERY` is reached.
- Issue 2 (Refund Safety): Starter code had missing checks for positive amounts, max refundable limits, and boolean values slipping past integer checks. Added strict validation.
- Issue 3 (Reconciliation): `reconcile_orders` ignored status differences and blindly grouped mismatched statuses as matched. Split amount and status checks into separate buckets.

## 4. Implementation decisions
- Main changes and why: Added strict type and value checks in `apply_order_event` and fixed discrepancy tracking in `reconcile_orders` to meet all safety rules.
- Alternatives considered and why rejected: Complex state machine libraries were rejected to keep the codebase lightweight and straightforward.
- Assumptions: Order totals and refund amounts are handled in integer paise.

## 5. Verification
- Tests added or changed: None of the existing test suite was bypassed or deleted; all starter tests now pass successfully.
- Commands run and actual results: `python3 -m pytest -q` -> All tests passed.
- Edge cases verified: Boolean refunds, zero-due refunds, post-dispatch cancellations, duplicate event replays, and status reconciliation.
- Remaining failures or known limitations: None.