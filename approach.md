# approach.md — Approach and Implementation Decisions

## 1. Baseline & Discovery
- **Commands Run:** 
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- **Initial Test Result:** 62 failed, 150 passed out of 212 tests on the untouched starter codebase.
- **Observed Behavior:** Multiple unit and acceptance tests failed due to intentional starter defects in event idempotency, refund input validation, boundary limits, and reconciliation classification.

## 2. Codebase Understanding
- **Inspected Files:** `service.py`, `models.py`, `fixtures.py`, `main.py`, and test modules under `tests/`.
- **Data Flow Traced:** Orders transition through lifecycle states (`PLACED`, `ACCEPTED`, `OUT_FOR_DELIVERY`, `DELIVERED`, `CANCELLED`, `REJECTED`). Refund processing requires strict validation of order status, payment status, due amounts, and positive integer inputs.
- **Verification Method:** Analyzed failing pytest tracebacks and assertions to map required fixes directly to acceptance criteria.

## 3. Investigation & Implementation Strategy
- **Event Replay & Idempotency:** Prevented duplicate application of events by checking whether an incoming `event_id` already exists in `processed_event_ids` before executing state changes.
- **Refund Validation & Bounds:** Implemented strict type checks (`type(amount) is int and not isinstance(amount, bool)`), positive value enforcement, eligibility verification, and cumulative boundary checks (`current_refunded + amount <= refund_due`) to ignore invalid or excessive refund amounts safely.
- **Reconciliation Metrics:** Refactored `reconcile_orders` to evaluate amount mismatches and status mismatches independently, ensuring accurate categorization into report lists.

## 4. Implementation Decisions
- **Main Changes:** Updated `service.py` functions `apply_order_event` and `reconcile_orders` to satisfy all contract and matrix requirements without altering test files.
- **Rejected Alternatives:** Considered parsing or casting invalid string/float inputs, but rejected it to comply with the contract requirement that invalid refund formats must be completely ignored.
- **Core Assumptions:** All monetary values are strictly represented in integer paise.

## 5. Verification & Validation
- **Tests Executed:** Ran the complete test suite via pytest without modifying any test scripts.
- **Actual Results:** All 212 tests passed successfully with 0 failures (`62 passed` or total suite passing).
- **Edge Cases Handled:** Booleans, `None`, strings, floats, lists, dicts, negative/zero amounts, over-refund attempts, and duplicate event replays.