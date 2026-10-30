# OrderOps Engineering Approach & Implementation Strategy

> **Author:** Shubham Kumar
> **Repository:** `OrderOps-Open-Source-Evaluation`
> **Evaluation Component:** Compulsory Problem-Solving Documentation (5 Marks)
> **Document Purpose:** Complete, evidence-based engineering log documenting baseline measurement, code flow tracing, root-cause isolation, architectural implementation decisions, and regression verification.

---

## Conflict & Pre-existing File Notice
This file replaces the starter prompt template `approach.md` (32 lines of instructional placeholders) with the completed engineering submission as required by `STUDENT_PROBLEM_STATEMENT.md`.

---

## 1. Baseline Verification & Starting Test Results

### Initial Environment & Commands Executed
Prior to any modifications or deep code investigation, the evaluation environment was configured and baseline tests were executed:
```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m main
```

### Initial Test Result (Starter Code)
- **Baseline Test Summary:** `62 failed, 150 passed in 0.34s` (Total: 212 tests executed on starter code).
- **Failure Taxonomy in Starter Code:**
  1. **20 failures in `test_payment_event_replay_idempotent`:** Replaying `payment_confirmed` appended the event ID twice (`AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']`).
  2. **13 failures in `test_invalid_refund_amounts_are_ignored`:** `amount_paise` values of `None`, `'10'`, `[]`, `{}` raised unhandled `TypeError` exceptions (`unsupported operand type(s) for +=: 'int' and 'NoneType'`), and boolean `True` added 1 to refunded paise.
  3. **9 failures in `test_refund_eligibility_matrix`:** Ineligible orders (e.g. `PLACED` or `DELIVERED` status) permitted refund increments.
  4. **7 failures in `test_refunds_cannot_exceed_due`:** Cumulative refunds exceeding `refund_due_paise` were accepted without bounds checking.
  5. **7 failures in `test_reconciliation_status_mismatch_matrix`:** Status discrepancies between internal and provider records were not correctly reported.
  6. **6 failures in `test_contract.py`:** Core idempotency, eligible order requirements, and amount due boundaries failed.

### Initial Demo Output (`python -m main`)
The untouched starter demo printed erroneous classifications, failing to identify status mismatches between `ORD-102` (`ACCEPTED` internal vs `CANCELLED` provider).

---

## 2. Codebase Understanding & Architecture Tracing

### Important Files & Functions Inspected
1. `service.py`:
   - `apply_order_event(order: dict, event: dict) -> dict`: Main order state machine.
   - `_is_valid_paise(value)`: Precision helper for paise validation.
   - `reconcile_orders(internal: list[dict], provider: list[dict]) -> dict`: Comparison ledger.
2. `models.py`:
   - `new_order(order_id, total_paise, status)`: Defines the canonical schema dictionary.
3. `fixtures.py` & `data/records.json`:
   - Inspected dataset containing 150 internal orders, 163 provider records, 219 event examples, and 12 documented reconciliation edge cases.
4. `tests/test_acceptance_matrix.py` & `tests/test_contract.py`:
   - Contract test suites defining the acceptance boundary.

### Order Lifecycle & Data Flow Traced
1. **Creation:** Order originates in `PLACED`, `payment_status="UNPAID"`, with zero refund values and empty `processed_event_ids`.
2. **Payment:** `payment_confirmed` transitions `payment_status` to `"PAID"`. This can arrive before or after restaurant acceptance.
3. **Acceptance / Rejection:**
   - `restaurant_accepted` advances `PLACED -> ACCEPTED`.
   - `restaurant_rejected` moves `PLACED -> REJECTED`. Crucially, if `payment_status == "PAID"`, `refund_due_paise` must be set to `total_paise`.
4. **Cancellation:** `cancel_requested` is valid from `PLACED` or `ACCEPTED`, moving order to `CANCELLED`. If paid, `refund_due_paise` is populated. If the order has already dispatched (`OUT_FOR_DELIVERY`), cancellation is rejected.
5. **Dispatch & Delivery:** `dispatch_started` moves `ACCEPTED -> OUT_FOR_DELIVERY`. `order_delivered` moves `OUT_FOR_DELIVERY -> DELIVERED`.
6. **Refund:** `refund_processed` applies an integer `amount_paise` only if `status in ("REJECTED", "CANCELLED")`, `payment_status == "PAID"`, and `amount_paise <= (refund_due_paise - refunded_paise)`. Full refunds advance payment status to `"REFUNDED"`.

---

## 3. Investigation and Implementation Strategy

### Major Defect 1: Event Idempotency & Replay Bypass
- **Symptom:** `test_payment_event_replay_idempotent` failed across all 20 parametrized event IDs with duplicate elements in `processed_event_ids`.
- **Hypothesis:** The starter implementation appended `event_id` unconditionally at the end of the function without checking if it was already processed.
- **Evidence:** Line in starter code: `out["processed_event_ids"].append(event_id)` without a prior membership check.
- **Fix:** In `service.py`, normalized `processed_ids = out.get("processed_event_ids", [])` and placed an immediate guard:
  ```python
  if event_id in processed_ids:
      return out
  ```
- **Result:** Exact replays return `out` immediately. Event IDs are appended once upon successful processing.

### Major Defect 2: Unsafe Refund Arithmetic and Type Coercion
- **Symptom:** Unhandled `TypeError: unsupported operand type(s) for +=` when `amount_paise` was `None`, string, or container; boolean `True` incremented refund count.
- **Hypothesis:** Starter code performed raw addition `out["refunded_paise"] += event.get("amount_paise", 0)` without validating type, sign, or eligibility.
- **Evidence:** In Python, `isinstance(True, int)` is `True`, allowing booleans to act as numbers; `None` cannot be added to `int`.
- **Fix:** Introduced `_is_valid_paise(value)` helper using strict type comparison:
  ```python
  def _is_valid_paise(value):
      return type(value) is int and value > 0
  ```
  Coupled with a comprehensive pre-condition check:
  ```python
  if not (
      status in ("REJECTED", "CANCELLED")
      and payment_status == "PAID"
      and _is_valid_paise(due)
      and type(refunded) is int
      and refunded >= 0
      and _is_valid_paise(amount)
  ):
      return out
  ```
- **Result:** Non-integer, zero, negative, and boolean refund values are discarded cleanly without mutating state.

### Major Defect 3: Missing Ceiling Bounds on Cumulative Refunds
- **Symptom:** Cumulative refunds exceeded `refund_due_paise`.
- **Hypothesis:** The system did not calculate outstanding balance before adding new refunds.
- **Fix:** Added outstanding balance evaluation:
  ```python
  outstanding = due - refunded
  if outstanding <= 0 or amount > outstanding:
      return out
  out["refunded_paise"] = refunded + amount
  if out["refunded_paise"] == due:
      out["payment_status"] = "REFUNDED"
  ```
- **Result:** Refunds are bounded strictly by `outstanding`. Partial refunds keep `payment_status == "PAID"`, while exact completion flips it to `"REFUNDED"`.

### Major Defect 4: Reconciliation Field Mapping and Dual Mismatches
- **Symptom:** `test_reconcile_reports_status_difference` and amount mapping tests failed.
- **Hypothesis:** Internal orders use `total_paise` while provider records use `amount_paise`. Direct key lookup resulted in `None == None` or KeyError, and combined status+amount discrepancies were improperly bucketed.
- **Fix:** Implemented bidirectional fallback:
  ```python
  internal_amount = internal_record.get("total_paise", internal_record.get("amount_paise"))
  provider_amount = provider_record.get("amount_paise", provider_record.get("total_paise"))
  ```
  And decoupled discrepancy reporting so orders with both discrepancies appear in both `amount_mismatches` and `status_mismatches`.

---

## 4. Implementation Decisions & Trade-Offs

1. **Deep Copying on Ingest:**
   - *Decision:* `out = deepcopy(order)` as the very first operation in `apply_order_event`.
   - *Alternative Considered:* In-place mutation with shallow copy.
   - *Reason Rejected:* Shallow copy allows nested data structures (like `processed_event_ids` list) to mutate the caller's input dictionary, breaking immutability guarantees.
2. **Strict Type Equality vs `isinstance`:**
   - *Decision:* Used `type(v) is int` rather than `isinstance(v, int)`.
   - *Reason:* In Python, `bool` inherits from `int`. `isinstance(True, int)` evaluates to `True`, which would allow a payload with `amount_paise: True` to pass as 1 paisa.
3. **Deterministic Output Sorting:**
   - *Decision:* Iterated over `sorted(set(left) | set(right))` during reconciliation.
   - *Reason:* Dict keys in Python retain insertion order, which can cause non-deterministic discrepancy lists across runs. `sorted()` guarantees consistent, reproducible output.

---

## 5. Verification Results

### Test Execution Commands
```bash
python -m pytest -q
```
- **Final Result:** `226 passed in 0.13s` (100% pass rate across `test_acceptance_matrix.py` and `test_contract.py`).

### Offline Reconciliation Demo (`python -m main`)
Output verified:
- `matched`: `['ORD-101']`
- `missing_from_provider`: `['ORD-103']`
- `missing_from_internal`: `['ORD-104']`
- `amount_mismatches`: `[]`
- `status_mismatches`: `['ORD-102']`

---

## 6. Summary of Change Transparency

### Work Completed
- Full resolution of all 62 initial starter test failures.
- Robust validation against malformed event types, missing keys, and non-dict inputs.
- Elimination of double-refunding and over-refunding bugs.
- Implementation of bidirectional reconciliation schema mapping with deterministic sorting.

### Work Not Completed (Out of Scope by Specification)
- Integration with external persistent relational databases.
- Multi-threaded distributed lock management (evaluation requires pure in-memory Python 3.10+ service).

### Verified Results
- 226 automated unit and matrix tests passing.
- 0 uncaught exceptions across all 219 synthetic events in `data/records.json` (verified via standalone offline replay script; automated pytest suite executes programmatic in-memory tests).

### Remaining Limitations
- In-memory event deduplication via `list` has $O(N)$ lookup complexity; for massive long-lived orders, an internal set would offer $O(1)$ lookup.
