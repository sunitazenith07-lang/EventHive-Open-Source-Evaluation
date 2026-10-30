# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
- Commands run before editing:
  - `python --version` (observed: `Python 3.13.14`)
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- Initial test result (include the actual summary):
  - Untouched baseline: `62 failed, 150 passed in 0.64s` (Total: 212 tests executed).
- Demo/output observed:
  ```
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  Both `ORD-101` and `ORD-102` were incorrectly classified as amount mismatches despite identical prices (45900 and 129900 paise), and `status_mismatches` was completely unpopulated.

## 2. Codebase understanding
- Important files and functions inspected:
  - `models.py`: Inspected `new_order()`. Observed default dictionary structure (`order_id`, `total_paise`, `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]`).
  - `service.py`:
    - `apply_order_event(order: dict, event: dict) -> dict`: Handled state transitions and refund math, but lacked deduplication guards, allowed negative/non-integer/excessive refunds, and missed status-based refund eligibility.
    - `reconcile_orders(internal: list[dict], provider: list[dict]) -> dict`: Reconciled transactions across systems, but only checked `amount_paise` (missing `total_paise` key aliases in internal orders) and omitted all status comparison logic.
  - `fixtures.py` and `data/records.json`: Inspected synthetic schema (150 internal orders, 163 provider records, 219 event instances, and edge-case catalog).
  - `tests/test_contract.py` & `tests/test_acceptance_matrix.py`: Analyzed the 212 contract and parametrized matrix tests to define acceptance boundaries.
- Order lifecycle or data flow traced:
  1. `PLACED` -> `ACCEPTED` (via `restaurant_accepted`) or `REJECTED` (via `restaurant_rejected`).
  2. `ACCEPTED` -> `OUT_FOR_DELIVERY` (via `dispatch_started`).
  3. `OUT_FOR_DELIVERY` -> `DELIVERED` (via `order_delivered`).
  4. Cancellation (`cancel_requested`) allowed only during `PLACED` or `ACCEPTED` states.
  5. Payment confirmed (`payment_confirmed`) sets `payment_status="PAID"`. If order was already rejected or cancelled, sets `refund_due_paise=total_paise`.
  6. Refunds (`refund_processed`) eligible only for cancelled/rejected orders with `payment_status="PAID"` and `refund_due_paise > 0`.
- How you confirmed your understanding:
  Traced failing pytest stack traces against `service.py` lines, compared the internal order model with provider records in `data/records.json`, and tested single event transitions in Python REPL.

## 3. Investigation and implementation strategy
For each major defect, describe the observed symptom, the hypothesis you tested, evidence from a test/log/example, and the fix chosen.

- Issue 1: Event Replay Duplicate Accumulation (Lack of Idempotency)
  - *Symptom:* Replaying an event resulted in duplicate entries in `processed_event_ids` (e.g., `['EV-000', 'EV-000'] == ['EV-000']` failed).
  - *Hypothesis:* `service.py` always executed `out["processed_event_ids"].append(event_id)` at the end without checking if `event_id` was already in `out["processed_event_ids"]`.
  - *Evidence:* 20 parametrized failures in `test_payment_event_replay_idempotent` and `test_duplicate_event_is_idempotent`.
  - *Fix:* Insert an early guard at the beginning of `apply_order_event`: `if event_id is not None and event_id in out["processed_event_ids"]: return out`. Append `event_id` at the end only if it is not None.

- Issue 2: Unchecked and Unbounded Refund Processing
  - *Symptom:* Negative refund amounts, boolean amounts (`True`/`False`), floats, refunds on unpaid/delivered orders, and refunds exceeding `refund_due_paise` were processed.
  - *Hypothesis:* `apply_order_event` blindly executed `out["refunded_paise"] += event.get("amount_paise", 0)` without eligibility or type checks.
  - *Evidence:* 13 failures in `test_invalid_refund_amounts_are_ignored`, 10 failures in `test_refund_eligibility_matrix`, and 7 failures in `test_refunds_cannot_exceed_due`.
  - *Fix:* Check eligibility: `status in ("REJECTED", "CANCELLED") and payment_status == "PAID" and due > 0`. Validate amount: `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`. Check remaining refundable capacity: `amount <= (due - refunded)`. Transition `payment_status` to `"REFUNDED"` only if `out["refunded_paise"] == due`.

- Issue 3: Flawed Reconciliation & Status Omission
  - *Symptom:* Mismatched order statuses were treated as matched, while internal orders with key `total_paise` were falsely reported as amount mismatches.
  - *Hypothesis:* `service.py` only checked `a.get("amount_paise") != b.get("amount_paise")`, which evaluated to `None != 45900` for `sample_orders()`, and the `else` branch unconditionally placed items into `matched` without checking status.
  - *Evidence:* `test_reconcile_reports_status_difference` failed, 7 parametrized failures in `test_reconciliation_status_mismatch_matrix`, and incorrect `python -m main` baseline output.
  - *Fix:* Resolve amount via `a.get("amount_paise") if a.get("amount_paise") is not None else a.get("total_paise")` (and likewise for `b`), compute both `amount_diff` and `status_diff`, and populate `amount_mismatches`, `status_mismatches`, and `matched` deterministically.

## 4. Implementation decisions
- Main changes and why:
  - Centralized idempotency guard before any mutation to guarantee immutability on replayed events.
  - Explicit boolean guard (`not isinstance(amount, bool)`) because in Python `bool` inherits from `int` (`isinstance(True, int) is True`).
  - Added support for both `amount_paise` and `total_paise` in reconciliation to unify models across internal domain objects and provider snapshots.
- Alternatives considered and why rejected:
  - *Alternative 1 (Throwing exceptions on duplicates or invalid refunds):* Rejected because the specification requires resilient handling without state corruption or crashes (`Handle empty input, missing fields, unknown IDs, invalid event types and duplicates without corrupting state`).
  - *Alternative 2 (Using floating point currency):* Rejected; integer paise avoids IEEE 754 precision issues (e.g., `0.1 + 0.2 != 0.3`).
- Assumptions:
  - Cancellations after `dispatch_started` must never transition to `CANCELLED` and receive zero refund.
  - If payment confirmation arrives after restaurant rejection, the full `total_paise` becomes refundable.

## 5. Verification
- Tests added or changed:
  - Maintained 100% of existing tests without alteration.
  - Created `tests/test_regression_and_edge_cases.py` with 10 comprehensive regression and stretch tests.
- Commands run and actual results:
  - `python -m pytest -q` -> `222 passed in 0.33s` (All 212 baseline + 10 new tests pass).
  - `python -m main` -> Correct demo output (`ORD-101` matched, `ORD-102` status mismatch, `ORD-103` missing from provider, `ORD-104` missing from internal, `amount_mismatches` empty).
- Edge cases verified:
  - Post-dispatch cancellation rejection (`OUT_FOR_DELIVERY` and `DELIVERED`).
  - Non-integer and boolean amount rejection (`True`, `False`, floats, strings).
  - Out-of-order event sequences (reject before payment confirmation).
  - Multiple partial refunds reaching exact total.
  - Simultaneous amount and status mismatch in reconciliation.
- Remaining failures or known limitations:
  - 0 remaining failures.
