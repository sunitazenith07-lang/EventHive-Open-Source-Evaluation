# Engineering Progress Report & Chronological Change Log

**Project:** OrderOps — Food-Delivery Order Lifecycle, Cancellation, Refunds, and Reconciliation  
**Participant:** Open-Source Contributor  
**Language & Environment:** Python 3.13.14 on Windows  

---

## Chronological Engineering Log

### Entry 1
- **Entry number:** 1
- **Time / duration:** 00:00 - 00:30 (30 mins)
- **File or module examined:** `README.md`, `STUDENT_PROBLEM_STATEMENT.md`, `STUDENT_START_HERE.md`, `models.py`, `fixtures.py`, `service.py`, `tests/test_contract.py`, `tests/test_acceptance_matrix.py`, `data/records.json`
- **Problem or behaviour investigated:** Initial repository orientation, architecture review, and establishing the untouched baseline.
- **Root-cause analysis:** N/A (Exploration & Baseline phase).
- **Change made by me:** Inspected files; executed `python --version`, `python -m pip install -r requirements-dev.txt`, `python -m pytest -q`, and `python -m main`.
- **Reason for the change:** Establish baseline execution status as mandated by the evaluation acceptance contract.
- **Tests performed:** Baseline `python -m pytest -q`.
- **Results observed:**
  - `python -m pytest -q`: `62 failed, 150 passed in 0.64s` (Total 212 tests).
  - `python -m main`:
    ```
    matched: []
    missing_from_provider: ['ORD-103']
    missing_from_internal: ['ORD-104']
    amount_mismatches: ['ORD-101', 'ORD-102']
    status_mismatches: []
    ```
- **Remaining issues:** 62 tests failing across event idempotency, refund eligibility, invalid refund amounts, and status reconciliation.
- **What I learned:** The starter code contained deliberate structural bugs in `apply_order_event` (lack of idempotency guards, unvalidated refunds) and `reconcile_orders` (missing status checks and `total_paise` key handling).

---

### Entry 2
- **Entry number:** 2
- **Time / duration:** 00:30 - 01:00 (30 mins)
- **File or module examined:** `service.py` (`apply_order_event`)
- **Problem or behaviour investigated:** Idempotency failure on event replay (`test_payment_event_replay_idempotent` failing 20 times; `test_duplicate_event_is_idempotent` failing).
- **Root-cause analysis:** `service.py` appended every incoming `event_id` to `processed_event_ids` at the end of `apply_order_event` without checking whether `event_id` was already in the list. On replay, the event re-executed and added a duplicate `event_id`.
- **Change made by me:** Added an early return check at the top of `apply_order_event`: `if event_id is not None and event_id in out["processed_event_ids"]: return out`. Only appended `event_id` if it was not None.
- **Reason for the change:** Enforce strict idempotency per Requirement 3: replaying an event must return the order unchanged and avoid duplicate IDs in `processed_event_ids`.
- **Tests performed:** Ran `pytest -k "idempotent"`.
- **Results observed:** All 21 idempotency tests passed immediately (`21 passed`).
- **Remaining issues:** Refund eligibility and reconciliation defects remain.
- **What I learned:** Early exit prevents not just duplicate ID tracking, but completely avoids redundant compute and unintentional state mutation on duplicate incoming webhook deliveries.

---

### Entry 3
- **Entry number:** 3
- **Time / duration:** 01:00 - 01:45 (45 mins)
- **File or module examined:** `service.py` (`apply_order_event` -> `kind == "refund_processed"`)
- **Problem or behaviour investigated:** Refunds were processed on ineligible orders (`PLACED`, `DELIVERED`, `UNPAID`), invalid amounts (`0`, `-10`, `True`, `0.5`, `"10"`), and amounts exceeding remaining refundable capacity.
- **Root-cause analysis:** Line 39 in the starter blindly executed `out["refunded_paise"] += event.get("amount_paise", 0)`. It lacked guards for order status (`REJECTED` or `CANCELLED`), `payment_status == "PAID"`, positive refund due, strict integer validation (excluding Python booleans), and maximum allowed refund ceiling (`due - refunded`).
- **Change made by me:**
  1. Guarded refund processing behind `status in ("REJECTED", "CANCELLED") and payment_status == "PAID" and due > 0`.
  2. Guarded amount behind `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`.
  3. Ensured `amount <= due - refunded`.
  4. Updated `payment_status` to `"REFUNDED"` only when cumulative `refunded_paise == due`.
  5. Handled out-of-order payment confirmation arriving after restaurant rejection/cancellation to set `refund_due_paise = total_paise`.
- **Reason for the change:** Enforce Requirements 4 and 5: integer paise safety, prevent over-refunding, protect partial refunds from prematurely marking `REFUNDED`, and ensure financial integrity.
- **Tests performed:** Ran `pytest -k "refund"`.
- **Results observed:** All 58 refund-related matrix and contract tests passed.
- **Remaining issues:** Reconciliation logic still failing on status mismatches and demo output.
- **What I learned:** In Python, `isinstance(True, int)` evaluates to `True` because `bool` inherits from `int`. Explicitly checking `not isinstance(amount, bool)` is crucial for bulletproof financial arithmetic.

---

### Entry 4
- **Entry number:** 4
- **Time / duration:** 01:45 - 02:15 (30 mins)
- **File or module examined:** `service.py` (`reconcile_orders`), `fixtures.py`, `main.py`
- **Problem or behaviour investigated:** Reconciliation failed to detect status differences (marking mismatched statuses as matched) and falsely reported `ORD-101` and `ORD-102` as amount mismatches in `main.py`.
- **Root-cause analysis:**
  1. `service.py` only compared `amount_paise`. Internal orders created by `new_order()` use `total_paise`, causing `a.get("amount_paise")` to return `None`.
  2. Status comparison was completely omitted; the `else` block automatically added orders to `matched` if amounts were equal.
- **Change made by me:**
  1. Fallback key resolution: `a.get("amount_paise") if a.get("amount_paise") is not None else a.get("total_paise")` (and same for `b`).
  2. Evaluated `amount_diff = (a_amount != b_amount)` and `status_diff = (a_status != b_status)`.
  3. Correctly appended keys to `amount_mismatches`, `status_mismatches`, or `matched`.
  4. Added defensive checks for empty/non-list inputs and missing `order_id` values.
- **Reason for the change:** Enforce Requirement 6: separate, deterministic reporting of missing records, amount mismatches, and status mismatches.
- **Tests performed:** `python -m pytest -q` and `python -m main`.
- **Results observed:**
  - `python -m pytest -q`: `212 passed in 0.22s` (100% of visible baseline tests pass).
  - `python -m main`:
    ```
    matched: ['ORD-101']
    missing_from_provider: ['ORD-103']
    missing_from_internal: ['ORD-104']
    amount_mismatches: []
    status_mismatches: ['ORD-102']
    ```
- **Remaining issues:** None in core functionality. Need regression tests, documentation, and stretch goal.
- **What I learned:** Heterogeneous schema contracts between internal systems and third-party gateways are a common real-world defect source; robust normalization prevents false alarms.

---

### Entry 5
- **Entry number:** 5
- **Time / duration:** 02:15 - 02:45 (30 mins)
- **File or module examined:** `service.py` (`export_awaiting_refund_csv`), `tests/test_regression_and_edge_cases.py`
- **Problem or behaviour investigated:** Adding regression tests for custom fixes and implementing the optional stretch feature.
- **Root-cause analysis:** Proactive regression coverage and operational tooling.
- **Change made by me:**
  1. Implemented stretch feature `export_awaiting_refund_csv(orders, filepath=None)` in `service.py`.
  2. Created `tests/test_regression_and_edge_cases.py` with 10 comprehensive tests covering cross-event idempotency, multi-stage partial refunds, type safety, late payment arrival, malformed inputs, dual mismatches, and CSV export.
- **Reason for the change:** Meet evaluation requirements for regression coverage and complete one operational stretch capability.
- **Tests performed:** Full suite `python -m pytest -q`.
- **Results observed:** `222 passed in 0.33s` (212 starter matrix tests + 10 regression/stretch tests).
- **Remaining issues:** All tests green.
- **What I learned:** Using standard library `csv` with `io.StringIO` allows seamless in-memory string generation as well as deterministic file output.

---

### Entry 6
- **Entry number:** 6
- **Time / duration:** 02:45 - 03:00 (15 mins)
- **File or module examined:** Documentation deliverables: `approach.md`, `challenges.md`, `optimizations.md`, `TESTING.md`, `ORDER_FLOW_NOTES.md`, `ARCHITECTURE.md`, `PROJECT_NOTES.md`
- **Problem or behaviour investigated:** Fulfilling all documentation requirements for evaluation submission.
- **Root-cause analysis:** Required by the 100-mark rubric.
- **Change made by me:** Authored complete, evidence-based markdown files describing real tests, actual reproduction outputs, and architectural reasoning.
- **Reason for the change:** Complete the mandatory 15-mark problem-solving deliverables and evaluation checklist.
- **Tests performed:** `python -m pytest -q`, `python -m main`, `git status`.
- **Results observed:** Clean test run (222 passed), demo output verified, all required documentation files present and complete.
- **Remaining issues:** None. Ready for walkthrough and submission.
- **What I learned:** Clear documentation linking root-cause analyses directly to test evidence provides transparency and reproducibility.

---

## Three-Hour Mark Summary (Presentation-Style Walkthrough)

### 1. Project Architecture and Data Flow
- **Order Lifecycle:** Orders are created via `new_order` (`PLACED`, `UNPAID`). The lifecycle transitions sequentially through `ACCEPTED`, `OUT_FOR_DELIVERY`, and `DELIVERED`. Cancellations are permitted only before dispatch (`PLACED` or `ACCEPTED`).
- **Payment & Refund Flow:** `payment_confirmed` sets `payment_status="PAID"`. Cancellations or rejections of paid orders initialize `refund_due_paise = total_paise`. As `refund_processed` events arrive, `refunded_paise` increments. Once `refunded_paise == refund_due_paise`, payment status transitions to `REFUNDED`.
- **Reconciliation Engine:** Compares internal orders against external provider settlement reports on `order_id`, normalizing key differences (`total_paise` vs `amount_paise`) and deterministically isolating amount mismatches, status mismatches, and missing records.

### 2. Initial Test Results
- **Command:** `python -m pytest -q`
- **Result:** `62 failed, 150 passed in 0.64s` (Total 212 tests).
- **Key Failure Areas:**
  - Idempotency replay (20 failures): `processed_event_ids` contained duplicate entries.
  - Invalid refund values (13 failures): negative numbers, floats, booleans, and overages processed.
  - Refund eligibility (10 failures): unpaid or active orders processed refunds.
  - Excessive refund checks (7 failures): cumulative refunds exceeded `refund_due_paise`.
  - Reconciliation status checks (7 failures): status mismatches marked as matched.
  - Offline demo (`main.py`): Matching order `ORD-101` erroneously flagged as an amount mismatch.

### 3. Issues Investigated
1. Duplicate event handling and append-order side effects.
2. Python `bool` subtyping `int` causing `True` to disburse 1 paise.
3. Unbounded cumulative refunds exceeding outstanding balances.
4. Schema discrepancy between internal (`total_paise`) and provider (`amount_paise`) dictionaries.
5. Incomplete reconciliation logic ignoring status mismatches.

### 4. Changes Personally Implemented
- **Idempotency Guard:** `if event_id is not None and event_id in out["processed_event_ids"]: return out`.
- **Refund Eligibility & Validation:** Multi-level guard verifying terminal status (`CANCELLED`/`REJECTED`), payment status (`PAID`), positive balance, positive integer paise (`isinstance(amount, int) and not isinstance(amount, bool)`), and remaining refund ceiling.
- **Reconciliation Normalization & Bi-criteria Comparison:** Dual key resolution for amounts, deterministic sorting, and accurate isolation of amount and status mismatches.
- **Stretch Feature:** Implemented `export_awaiting_refund_csv` to generate operational CSV reports for pending refunds.
- **Regression Suite:** Added 10 extensive tests in `tests/test_regression_and_edge_cases.py`.

### 5. Tests Run and Their Results
- Untouched baseline: `62 failed, 150 passed in 0.64s`
- Post-fix test run: `222 passed in 0.33s` (0 failures, 100% pass rate).
- Demo run: `python -m main` outputs clean, verified reconciliation dictionary.

### 6. Current Limitations and Next Priorities
- **Limitation 1 (Null Event IDs):** Events without an `event_id` cannot be deduplicated; upstream event brokers must ensure event IDs are generated.
- **Limitation 2 (Reconciliation Grouping):** `reconcile_orders` assumes a single summary entry per order ID. Future priority would be aggregating multi-transaction provider ledgers.

### 7. Technical Concepts I Can Explain During a Live Walkthrough
- **Idempotent Webhook Processing:** Why and how event deduplication using persistent event IDs protects against duplicate charges and refunds.
- **State Machine Invariants:** Why cancellations must be prohibited post-dispatch to protect physical inventory and logistics commitments.
- **Integer Currency Arithmetic:** Avoiding IEEE 754 floating-point inaccuracies by standardizing on integer paise.
- **Python Type Safety Edge Cases:** Why `isinstance(True, int)` is `True` and how to prevent boolean coercion in financial logic.
- **Multi-Way Deterministic Reconciliation:** Hash-map based $O(N \log N)$ reconciliation isolating missing entries, status mismatches, and amount discrepancies.
