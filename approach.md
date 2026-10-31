# approach.md - Engineering Approach and Decisions

## 1. Baseline
- **Commands run before editing**:
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result**:
  - 62 failed, 150 passed in 1.02s (total 212 tests).
  - Primary failure clusters:
    - 20 failures in `test_payment_event_replay_idempotent` (duplicate event replay was not idempotent).
    - 13 failures in `test_invalid_refund_amounts_are_ignored` (negative, float, bool, None, over-limit amounts were accepted).
    - 10 failures in `test_refund_eligibility_matrix` (unpaid, placed, accepted, delivered, and already refunded orders were erroneously processed for refunds).
    - 7 failures in `test_refunds_cannot_exceed_due` (refunds exceeding due amount were added instead of ignored).
    - 7 failures in `test_reconciliation_status_mismatch_matrix` (status mismatches were incorrectly classified as matched).
    - 5 failures in `tests/test_contract.py` (`test_duplicate_event_is_idempotent`, `test_refund_requires_eligible_order`, `test_refund_must_be_positive`, `test_refund_cannot_exceed_amount_due`, `test_reconcile_reports_status_difference`).
- **Demo/output observed**:
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  In the demo, ORD-101 and ORD-102 were falsely flagged as amount mismatches because internal orders store `total_paise` rather than `amount_paise`, and ORD-102 status mismatch was completely missed.

## 2. Codebase understanding
- **Important files and functions inspected**:
  - `service.py`: `apply_order_event` (core event state machine) and `reconcile_orders` (internal vs provider summary reconciliation).
  - `models.py`: `new_order` defining the default structure: `order_id`, `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise`, `processed_event_ids`.
  - `fixtures.py` and `main.py`: Offline sample datasets and reconciliation runner.
  - `tests/test_acceptance_matrix.py` & `tests/test_contract.py`: Comprehensive acceptance tests defining valid state transitions, idempotency rules, refund boundaries, and reconciliation matrices.
  - `data/records.json` & `data/README.txt`: 150 orders, 163 provider records, 219 synthetic events, and edge case specifications.
- **Order lifecycle or data flow traced**:
  - Order Status: `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`.
  - Cancellation / Rejection: `PLACED` -> `REJECTED`; `PLACED` or `ACCEPTED` -> `CANCELLED`. Cancellation after dispatch is invalid and ignored.
  - Payment & Refund: `UNPAID` -> `PAID` -> `REFUNDED`. Rejection/cancellation of a paid order marks `refund_due_paise = total_paise`. If payment confirmation arrives after rejection/cancellation, `refund_due_paise` must also be set. Refunds are only allowed if paid and rejected/cancelled, strictly bounded by remaining refundable balance.
- **How understanding was confirmed**:
  - Cross-referenced all assertions across `test_acceptance_matrix.py` and `test_contract.py` against `STUDENT_PROBLEM_STATEMENT.md` requirements.
  - Traced data schemas in `records.json` to verify property names (`total_paise` vs `amount_paise`).

## 3. Investigation and implementation strategy
- **Issue 1: Missing Event Idempotency**:
  - *Symptom*: Replaying any event appended duplicate IDs to `processed_event_ids` and allowed state mutations to repeat.
  - *Hypothesis*: The function lacked an early membership check for `event_id` in `processed_event_ids`.
  - *Evidence*: `test_payment_event_replay_idempotent` asserted `twice["processed_event_ids"] == [event_id]`, but received `[event_id, event_id]`.
  - *Fix*: Check `event_id = event.get("event_id")`. If `event_id is not None and event_id in out["processed_event_ids"]`, return `out` immediately. Only append `event_id` if it is not None.
- **Issue 2: Unchecked Refund Processing**:
  - *Symptom*: Negative values, booleans (`True` which is an `int` subclass in Python), floats, non-numeric amounts, and amounts exceeding refundable due were applied. Furthermore, unpaid or placed orders were given refunds, and `payment_status` was prematurely marked `REFUNDED` when `refund_due_paise` was 0.
  - *Hypothesis*: `refund_processed` lacked guards for order eligibility, amount data type, strictly positive value, and remaining balance ceiling.
  - *Evidence*: 30 test failures across invalid refund amounts, eligibility matrix, and refund ceilings.
  - *Fix*:
    1. Guard eligibility: `out.get("status") in ("REJECTED", "CANCELLED") and out.get("payment_status") == "PAID"`.
    2. Guard amount type and value: `type(amount) is int and amount > 0`.
    3. Guard remaining balance: `remaining_due = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)`. Only accept when `amount <= remaining_due`.
    4. Only flip `out["payment_status"] = "REFUNDED"` when `out["refunded_paise"] >= out.get("refund_due_paise", 0)`.
- **Issue 3: Reconciliation Missing Status Mismatch and Key Normalization**:
  - *Symptom*: In `reconcile_orders`, orders with different statuses but same amount were placed in `matched`. In addition, internal order objects with `total_paise` were compared to provider `amount_paise`, causing false amount mismatches.
  - *Hypothesis*: `reconcile_orders` checked only `amount_paise` on `a` and completely lacked a status check branch.
  - *Evidence*: `test_reconciliation_status_mismatch_matrix` failed on every status mismatch pair. `main.py` placed `ORD-101` and `ORD-102` in `amount_mismatches`.
  - *Fix*: Implemented `_get_amount(record)` checking `"amount_paise"` if present and non-None, falling back to `"total_paise"`. Evaluated both `has_amount_mismatch` and `has_status_mismatch` independently, reporting to `amount_mismatches` and `status_mismatches` respectively, and appending to `matched` only when both match. Added input type guards for malformed or non-dict records.

## 4. Implementation decisions
- **Main changes and why**:
  - Preserved pure functional behavior: input orders are never mutated (`deepcopy(order)` is used).
  - Used exact type checking `type(amount) is int` rather than `isinstance(amount, int)` because in Python `isinstance(True, int)` is True, which would permit boolean values.
  - Supported dual-field amount extraction in reconciliation so both `new_order` internal records (`total_paise`) and transaction summary records (`amount_paise`) reconcile seamlessly.
  - Accommodated late-arriving payment confirmations (`payment_confirmed` on an order already `CANCELLED` or `REJECTED`) by properly initializing `refund_due_paise = total_paise`.
- **Alternatives considered and why rejected**:
  - *Alternative: Raising exceptions on duplicate events or invalid refunds*. Rejected because event ingestion systems should handle out-of-order or duplicate events gracefully (idempotency) rather than crashing or throwing unhandled errors.
  - *Alternative: Clamping refund amounts to remaining due instead of ignoring*. Rejected because the acceptance matrix tests explicitly require that over-refund attempts are rejected (`two["refunded_paise"] == first`), not partially capped.
- **Assumptions**:
  - Event IDs when provided are unique identifiers. Events without an `event_id` are processed but cannot be tracked for duplicate rejection.
  - All currency is represented in positive integer paise.

## 5. Verification
- **Tests added or changed**:
  - Untouched existing test files to preserve acceptance integrity.
  - Added `tests/test_regression.py` containing 8 dedicated tests:
    - `test_duplicate_event_idempotency_preserves_single_record`
    - `test_refund_rejection_for_boolean_amount`
    - `test_cumulative_partial_refunds_transition_to_refunded_on_exact_completion`
    - `test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due`
    - `test_cancellation_after_dispatch_and_delivery_is_strictly_ignored`
    - `test_malformed_and_none_events_do_not_corrupt_state`
    - `test_reconciliation_detects_simultaneous_amount_and_status_mismatch`
    - `test_reconciliation_with_total_paise_and_malformed_entries`
- **Commands run and actual results**:
  - `python -m pytest -v`: 220 passed in 0.42s (100% passing).
  - `python -m main`:
    ```text
    matched: ['ORD-101']
    missing_from_provider: ['ORD-103']
    missing_from_internal: ['ORD-104']
    amount_mismatches: []
    status_mismatches: ['ORD-102']
    ```
- **Edge cases verified**:
  - Multiple partial refunds adding up to exact total.
  - Rejection of refunds exceeding remaining balance.
  - Rejection of boolean values (`True`/`False`) as refund amounts.
  - Non-dict / malformed events and missing event IDs.
  - Reconciling orders with both amount mismatch and status mismatch simultaneously.
- **Remaining failures or known limitations**:
  - 0 test failures remain.
  - Concurrency/thread-safety is handled at the application level; in-memory dictionaries are not thread-locked.
