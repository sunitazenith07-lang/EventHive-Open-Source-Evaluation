# approach.md — Implementation Approach & Engineering Decisions

## 1. Baseline
- **Commands run before editing:**
  - `python3 -m pip install -r requirements-dev.txt` (installed `pytest-9.2.0`, `pluggy-1.7.0`, `iniconfig-2.3.1`, `packaging-26.3`, `pygments-2.21.0` under Python 3.15.2)
  - `python3 -m pytest -q`
  - `python3 -m main`
- **Initial test result (untouched starter):**
  - `62 failed, 150 passed in 0.30s` (total 212 tests)
  - Failing test categories:
    - 20 idempotency replay tests (`test_payment_event_replay_idempotent[EV-000]` through `[EV-019]`)
    - 15 invalid refund amount tests (`test_invalid_refund_amounts_are_ignored`)
    - 10 refund eligibility matrix tests (`test_refund_eligibility_matrix`)
    - 7 refund limit tests (`test_refunds_cannot_exceed_due`)
    - 5 contract tests (`test_duplicate_event_is_idempotent`, `test_refund_requires_eligible_order`, `test_refund_must_be_positive`, `test_refund_cannot_exceed_amount_due`, `test_reconcile_reports_status_difference`)
    - 5 status mismatch matrix tests (`test_reconciliation_status_mismatch_matrix`)
- **Demo/output observed on starter:**
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  `ORD-101` and `ORD-102` were falsely categorized as amount mismatches, and `status_mismatches` was completely unpopulated.

## 2. Codebase Understanding
- **Important files and functions inspected:**
  - `service.py`: Contains `apply_order_event()` for state updates and `reconcile_orders()` for cross-system reconciliation.
  - `models.py`: Defines `new_order()`, creating standard internal order dictionaries keyed with `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise`, and `processed_event_ids`.
  - `fixtures.py` & `main.py`: Provides offline demo data with internal orders (`total_paise`) and provider records (`amount_paise`).
  - `tests/test_contract.py` & `tests/test_acceptance_matrix.py`: Acceptance test suites covering transition permutations, replay idempotency, refund bounds, and reconciliation matrices.
  - `data/records.json`: Synthetic dataset containing 150 internal orders, 163 provider records, 219 event examples, and an edge-case catalog.
  - `.github/workflows/tests.yml`: Automated CI workflow validating test execution and publishing JUnit XML summaries.
- **Order lifecycle and data flow traced:**
  - Events supported: `payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, `refund_processed`.
  - State machine:
    - Normal progression: `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`.
    - Terminal cancellation/rejection: `PLACED` -> `REJECTED`, `PLACED` -> `CANCELLED`, `ACCEPTED` -> `CANCELLED`.
    - Invariant: Once an order reaches `OUT_FOR_DELIVERY` or `DELIVERED`, cancellation requests must be rejected.
  - Payment and refund flow:
    - Payment transitions: `UNPAID` -> `PAID` -> `REFUNDED`.
    - If a paid order is cancelled or rejected (or if payment confirms after cancellation/rejection), `refund_due_paise` equals `total_paise`.
    - Refunds must be positive integer paise, eligible only on paid cancelled/rejected orders, cannot exceed `refund_due_paise - refunded_paise`, and set `payment_status = "REFUNDED"` strictly when `refunded_paise == refund_due_paise`.
- **How understanding was confirmed:**
  - By cross-referencing failing assertions in `test_acceptance_matrix.py` against the requirement clauses in `STUDENT_PROBLEM_STATEMENT.md`.

## 3. Investigation and Implementation Strategy
- **Issue 1: Missing Event Idempotency**
  - *Observed symptom:* In `test_duplicate_event_is_idempotent` and `test_payment_event_replay_idempotent`, replaying an event appended the duplicate `event_id` to `processed_event_ids` (`assert ['EV-000', 'EV-000'] == ['EV-000']`).
  - *Hypothesis:* The starter code unconditionally appended `event_id` to `processed_event_ids` on line 43 without checking if `event_id` had already been processed.
  - *Fix:* Added an upfront guard at the start of `apply_order_event`:
    ```python
    if event_id is not None and event_id in out["processed_event_ids"]:
        return out
    ```
    This immediately halts further processing and returns the unmutated state copy on duplicates.

- **Issue 2: Unsafe and Unbounded Refund Processing**
  - *Observed symptom:* `test_invalid_refund_amounts_are_ignored`, `test_refund_eligibility_matrix`, and `test_refunds_cannot_exceed_due` failed. Negative numbers (`-10`), booleans (`True`), non-integers (`0.5`), and amounts exceeding `refund_due_paise` were added to `refunded_paise`.
  - *Hypothesis:* `service.py` had no validation for status eligibility, amount data type, positive integer constraint, or outstanding balance checks.
  - *Fix:*
    1. Validate eligibility: `out.get("status") in ("REJECTED", "CANCELLED") and out.get("payment_status") == "PAID" and out.get("refund_due_paise", 0) > 0`.
    2. Validate amount type & value: `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`.
    3. Check against outstanding balance: `outstanding = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)`. If `amount <= outstanding`, increment `refunded_paise`.
    4. Transition `payment_status` to `"REFUNDED"` only when `refunded_paise == refund_due_paise`.

- **Issue 3: Reconciliation Missing Status Validation and Schema Discrepancy**
  - *Observed symptom:* `test_reconcile_reports_status_difference` and `test_reconciliation_status_mismatch_matrix` failed. In the demo, `ORD-101` and `ORD-102` were reported as amount mismatches instead of being matched or status-mismatched.
  - *Hypothesis:* Starter `reconcile_orders` never compared status and assumed every order record contained `amount_paise`. Internal orders constructed with `new_order()` or from `data/records.json` use `total_paise`.
  - *Fix:*
    1. Implemented a helper `_get_amount(record)` that resolves `amount_paise` if present, falling back to `total_paise`.
    2. Extracted `has_amount_mismatch = (amount_a != amount_b)` and `has_status_mismatch = (status_a != status_b)`.
    3. Appended order IDs to `amount_mismatches` and/or `status_mismatches` independently, appending to `matched` strictly when neither mismatches.

## 4. Implementation Decisions
- **Immutability and Defensive Copying:** Kept `deepcopy()` on input orders to guarantee caller dictionary immutability as asserted by `test_input_order_is_not_mutated`.
- **Python Boolean Trap Guard:** Explicitly guarded with `not isinstance(amount, bool)` because in Python `isinstance(True, int)` evaluates to `True`.
- **Dual Mismatch Categorization:** Designed reconciliation so that records differing in both amount and status (such as `ORD-1078` in `records.json`) are recorded in both mismatch lists rather than short-circuiting.
- **Stretch Feature Choice:** Implemented `export_awaiting_refund_csv(orders)` to generate operational CSV reports for finance teams tracking outstanding refunds.

## 5. Verification
- **Tests added or changed:**
  - Preserved all 212 baseline tests without weakening or skipping.
  - Added `tests/test_regression.py` containing 9 new test suites covering conflicting replay payloads, late payment arrivals, post-dispatch cancellation blocking, multi-step partial refund series, malformed inputs, dual reconciliation mismatches, the full 150-order synthetic dataset from `data/records.json`, and CSV export.
- **Commands run and actual results:**
  - `python3 -m pytest -q` -> `221 passed in 0.09s` (0 failures, 0 warnings).
  - `python3 -m main` -> Correct demo output:
    ```text
    matched: ['ORD-101']
    missing_from_provider: ['ORD-103']
    missing_from_internal: ['ORD-104']
    amount_mismatches: []
    status_mismatches: ['ORD-102']
    ```
- **Edge cases verified:**
  - Conflicting payload replay under identical `event_id` is ignored.
  - Payment confirmed event arriving after restaurant rejection or customer cancellation properly populates `refund_due_paise`.
  - Duplicate payment confirmation cannot revert an order marked `REFUNDED` back to `PAID`.
  - Non-integer amounts (`True`, `False`, strings, negative amounts) are discarded.
  - Reconciliation against all 150 internal orders and 163 provider records in `data/records.json` yields exact expected partition (107 matched, 12 missing from provider, 25 missing from internal, 20 amount mismatches, 12 status mismatches).
- **Remaining failures or known limitations:**
  - None. All 221 tests pass with 100% success rate.
