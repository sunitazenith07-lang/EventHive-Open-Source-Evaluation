# approach.md - Required submission

## 1. Baseline
- Commands run before editing: `python -m pytest -q` and `python -m main`
- Initial test result: `62 failed, 150 passed, 1 warning (212 total tests)`
- Demo/output observed:
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```

## 2. Codebase understanding
- Important files and functions inspected:
  - `models.py`: `new_order()` defining dictionary schema with keys `order_id`, `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise`, `processed_event_ids`.
  - `service.py`: `apply_order_event()` for event processing/state machine and `reconcile_orders()` for provider comparison.
  - `fixtures.py` & `main.py`: Sample data and entry point for demo execution.
  - `tests/test_contract.py` & `tests/test_acceptance_matrix.py`: Contract and parametrized matrix test suites.
- Order lifecycle or data flow traced:
  `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`. If cancelled before dispatch or rejected by restaurant when paid, status changes to `CANCELLED` or `REJECTED` and `refund_due_paise` is populated with `total_paise`.
- How you confirmed your understanding: Traced test assertions in `test_acceptance_matrix.py` across state transitions, refund boundaries, and reconciliation matrices.

## 3. Investigation and implementation strategy
- Issue 1 (Idempotency):
  - *Symptom:* `test_payment_event_replay_idempotent` failed because replaying an event added duplicate event IDs to `processed_event_ids`.
  - *Hypothesis:* The service lacked a duplicate check before processing.
  - *Fix:* Added `if event_id is not None and event_id in out["processed_event_ids"]: return out`.
- Issue 2 (Refund Validation & Bounds):
  - *Symptom:* Non-positive, non-integer, and over-limit refunds were accepted on ineligible orders.
  - *Hypothesis:* `refund_processed` lacked guards for eligibility (`CANCELLED`/`REJECTED`, `PAID`, `refund_due_paise > 0`), type validation, and remaining balance checks.
  - *Fix:* Validated eligibility, ensured `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`, and capped refund increments to `refund_due_paise - refunded_paise`.
- Issue 3 (Reconciliation Flaws):
  - *Symptom:* `ORD-102` (status mismatch) was categorized as `matched` if amounts matched, and `new_order` dictionaries failed amount matching because they used `total_paise` instead of `amount_paise`.
  - *Hypothesis:* `reconcile_orders` failed to inspect `status` and only looked up `amount_paise`.
  - *Fix:* Read amount from either `amount_paise` or `total_paise`, checked both amount equality and status equality, and populated `status_mismatches` and `amount_mismatches` independently.

## 4. Implementation decisions
- Main changes and why: Focused exclusively on `service.py` to keep logic centralized, readable, and compliant with all behavioral contracts.
- Alternatives considered and why rejected: Considered raising exceptions on invalid events or invalid refund amounts, but rejected this because the problem statement specifies handling malformed events gracefully without corrupting state or halting execution.
- Assumptions: All currency values are strictly non-negative integers in paise; event replays with identical event IDs should be treated as no-ops.

## 5. Verification
- Tests added or changed: Added 3 regression tests in `tests/test_contract.py` (`test_regression_boolean_refund_is_rejected`, `test_regression_total_paise_reconciliation`, `test_regression_dual_mismatch`).
- Commands run and actual results:
  - `python -m pytest -q` -> `215 passed, 1 warning in 0.29s`
  - `python -m main` -> Correct demo output with `ORD-101` matched, `ORD-102` in status mismatches, `ORD-103` missing from provider, `ORD-104` missing from internal.
- Edge cases verified: Boolean amounts, negative/zero refund amounts, out-of-order cancellations, duplicate event replays, partial vs full refund completion.
- Remaining failures or known limitations: 0 failures.
