# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
- Commands run before editing:
  - `python --version` (Python 3.13.15)
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- Initial test result (include the actual summary):
  - `62 failed, 150 passed in 1.21s` (Total: 212 tests executed).
- Demo/output observed:
  ```
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  Note: In the starter demo, `ORD-101` and `ORD-102` were incorrectly classified as amount mismatches instead of evaluating matching amounts and detecting status mismatch for `ORD-102`.

## 2. Codebase understanding
- Important files and functions inspected:
  - `service.py`: Contains `apply_order_event(order, event)` and `reconcile_orders(internal, provider)`.
  - `models.py`: Helper `new_order(order_id, total_paise, status="PLACED")` returning canonical dictionary representation.
  - `fixtures.py` and `data/records.json`: Synthetic datasets representing internal orders, provider reports, lifecycle events, and edge cases.
  - `tests/test_contract.py` & `tests/test_acceptance_matrix.py`: Contract tests and parameterized test suites covering status transitions, event idempotency, refund bounds, and reconciliation matrices.
- Order lifecycle or data flow traced:
  - Lifecycle: `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`.
  - Rejections/Cancellations:
    - `restaurant_rejected` valid only from `PLACED` -> `REJECTED`.
    - `cancel_requested` valid only from `PLACED` or `ACCEPTED` -> `CANCELLED`. Cancellation attempted after dispatch (`OUT_FOR_DELIVERY` or `DELIVERED`) is rejected and does not mutate status.
    - If payment status is `PAID` upon rejection/cancellation (or if payment arrives after rejection/cancellation), `refund_due_paise` is populated with `total_paise`.
  - Refunds:
    - Processed only on eligible orders (`REJECTED` or `CANCELLED` with `PAID` payment status and positive `refund_due_paise`).
    - Amount must be strictly integer paise, positive, and <= outstanding refundable balance (`refund_due_paise - refunded_paise`).
    - Sets `payment_status = "REFUNDED"` only when `refunded_paise >= refund_due_paise`.
  - Reconciliation:
    - Joins records on `order_id`. Reports missing provider records, missing internal records, amount differences, and status differences deterministically.
- How you confirmed your understanding:
  - Traced failing tests in `tests/test_contract.py` and parameterized tests in `tests/test_acceptance_matrix.py` to identify exact edge conditions and failure assertions.
  - Inspected `data/records.json` edge case catalog and schema to verify provider vs internal order field naming conventions (`total_paise` vs `amount_paise`).

## 3. Investigation and implementation strategy
For each major defect, describe the observed symptom, the hypothesis you tested, evidence from a test/log/example, and the fix chosen.
- Issue 1: Lack of Event Idempotency
  - Observed Symptom: Replaying an event appended duplicate IDs to `processed_event_ids` and re-executed side effects (e.g., 20 tests in `test_payment_event_replay_idempotent` failed with `AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']`).
  - Hypothesis: `apply_order_event` lacked an early return check against `out["processed_event_ids"]`.
  - Evidence: `service.py` directly executed transitions and unconditionally appended `event_id` at the end of the function without deduplication.
  - Fix Chosen: Implemented an idempotency check at the top of `apply_order_event`: if `event_id is not None and event_id in out["processed_event_ids"]`, return `out` immediately. Only append non-null event IDs to `processed_event_ids`.
- Issue 2: Unsafe and Unbounded Refund Processing
  - Observed Symptom: `refund_processed` applied refunds to ineligible orders (e.g. `PLACED`, `ACCEPTED`, `UNPAID`), accepted non-positive amounts, non-integer amounts (including booleans), and permitted refunds exceeding `refund_due_paise`.
  - Hypothesis: Refund logic lacked eligibility validation (order state and payment state), integer paise type checking (`type(amount) is int`), positive bounds, and cumulative balance checks against `refund_due_paise - refunded_paise`.
  - Evidence: `test_refund_requires_eligible_order`, `test_refund_must_be_positive`, `test_refund_cannot_exceed_amount_due`, and acceptance matrix parametrized refund tests failed.
  - Fix Chosen: Checked `is_eligible = (out.get("status") in ("REJECTED", "CANCELLED") and out.get("payment_status") == "PAID" and out.get("refund_due_paise", 0) > 0)`. Validated that `type(amount) is int and amount > 0` and `amount <= (out["refund_due_paise"] - out["refunded_paise"])`. Only when valid is `refunded_paise` incremented, and status updated to `REFUNDED` if full amount reached.
- Issue 3: Flawed Reconciliation Logic & Amount/Status Mismatch Reporting
  - Observed Symptom: Status mismatches were masked as matched if amounts matched (`test_reconcile_reports_status_difference` failed). Also, internal order records using `total_paise` failed amount comparison against provider records using `amount_paise`.
  - Hypothesis: `reconcile_orders` checked `a.get("amount_paise") != b.get("amount_paise")` without checking `total_paise` or checking `status` differences.
  - Evidence: In `service.py`, `else: report["matched"].append(key)` was run whenever amounts matched, completely ignoring status differences.
  - Fix Chosen: Extracted amount using `_extract_amount(record)` checking both `amount_paise` and `total_paise`. Evaluated `has_amount_diff` and `has_status_diff` independently. If either or both differ, added key to `amount_mismatches` and/or `status_mismatches`. Added key to `matched` strictly when neither differed.

## 4. Implementation decisions
- Main changes and why:
  - Guarded against malformed inputs: added defensive checks for non-dict orders/events and missing `order_id` in reconciliation datasets.
  - Handled late payment events: if payment confirmation arrives after rejection/cancellation while unpaid, updated `payment_status` to `PAID` and populated `refund_due_paise` from `total_paise`.
  - Implemented stretch work `summarise_orders_by_state(orders)`: generates deterministic summary dictionary counting orders by lifecycle status.
- Alternatives considered and why rejected:
  - Raising exceptions on invalid events or over-refunds: Rejected because the problem statement dictates resilient handling without corrupting state or halting pipeline execution.
  - Using `isinstance(amount, int)`: Rejected because in Python, `bool` is a subclass of `int` (`isinstance(True, int) == True`). Used `type(amount) is int` to reject booleans safely.
- Assumptions:
  - Valid order state lifecycle adheres to `PLACED -> ACCEPTED -> OUT_FOR_DELIVERY -> DELIVERED`.
  - Cancellations after dispatch (`OUT_FOR_DELIVERY` or `DELIVERED`) are ignored.
  - Reconciliation must sort order IDs deterministically using `sorted(..., key=lambda x: str(x))`.

## 5. Verification
- Tests added or changed:
  - Untouched existing tests preserved completely without modification.
  - Added `tests/test_regression.py` containing 8 targeted regression tests:
    - Simultaneous amount and status mismatch.
    - Reconciliation handling of internal `total_paise`.
    - Late payment on previously cancelled/rejected orders.
    - Idempotency on replayed refund events.
    - Cumulative partial refunds and over-refund rejection.
    - Defensive handling of malformed inputs and missing keys.
    - Boolean amount rejection in refund processing.
    - Stretch feature `summarise_orders_by_state` validation.
- Commands run and actual results:
  - `python -m pytest -q` -> `220 passed in 0.33s`
  - `python -m main` -> Correctly matched `ORD-101`, reported missing `ORD-103`/`ORD-104`, and flagged status mismatch on `ORD-102`.
- Edge cases verified:
  - Replay of identical events with same `event_id`.
  - Partial refunds followed by exact full refund completion.
  - Over-refund attempt on already fully refunded orders.
  - Non-integer amounts (`0.5`, `"10"`, `True`, `False`, `None`).
  - Cancellation requested after dispatch initiation.
- Remaining failures or known limitations:
  - 0 test failures remaining; 100% test pass rate across 220 tests.