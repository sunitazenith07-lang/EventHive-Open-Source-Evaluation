# approach.md - Required submission

## 1. Baseline
- Commands run before editing:
  - `py -m pytest -q`
  - `py -m main`
- Initial test result (include the actual summary):
  - `62 failed, 150 passed, 1 warning in 0.53s` (collected 212 items)
- Demo/output observed:
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  `ORD-101` and `ORD-102` were falsely categorized as amount mismatches because internal orders used `total_paise` while provider records used `amount_paise`. Additionally, `ORD-102` status differences were ignored.

## 2. Codebase understanding
- Important files and functions inspected:
  - `service.py`: Contains `apply_order_event` (lifecycle state machine and refund processing) and `reconcile_orders` (reconciliation between internal and provider records).
  - `models.py`: Defines `new_order` constructor returning default order dictionary schema.
  - `fixtures.py` and `main.py`: Sample data and executable script for the offline reconciliation demonstration.
  - `tests/test_acceptance_matrix.py` and `tests/test_contract.py`: Comprehensive test matrices testing state transitions, idempotency, refund eligibility, amount validation, and reconciliation edge cases.
- Order lifecycle or data flow traced:
  - Orders begin as `PLACED` with `payment_status="UNPAID"`.
  - Events (`payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, `refund_processed`) transition states and update financial fields (`refund_due_paise`, `refunded_paise`).
  - Cancellation is only valid before dispatch (`PLACED` or `ACCEPTED`). Once `OUT_FOR_DELIVERY`, cancellation must be rejected.
- How you confirmed your understanding:
  - Traced failure stack traces from pytest and correlated them directly against assertions in `test_acceptance_matrix.py` and `test_contract.py`.

## 3. Investigation and implementation strategy
For each major defect, describe the observed symptom, the hypothesis you tested, evidence from a test/log/example, and the fix chosen.
- Issue 1: Missing Event Idempotency
  - Symptom: Replaying the same event caused duplicate IDs in `processed_event_ids`.
  - Hypothesis: `apply_order_event` appended `event_id` unconditionally without verifying if it already existed in `processed_event_ids`.
  - Evidence: `test_payment_event_replay_idempotent` failed with `AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']`.
  - Fix: Added an idempotency guard at the beginning of `apply_order_event`: `if event_id is not None and event_id in out["processed_event_ids"]: return out`.
- Issue 2: Unsafe Refund Processing and Type/Eligibility Validation
  - Symptom: Negative, zero, float, boolean, and excessive refund amounts were processed. Orders that were unpaid or in non-terminal states were also receiving refunds.
  - Hypothesis: Refund handler was performing raw addition `out["refunded_paise"] += event.get("amount_paise", 0)` without validating integer paise, positive bounds, order status, or outstanding refund balance.
  - Evidence: Failures in `test_invalid_refund_amounts_are_ignored`, `test_refund_eligibility_matrix`, and `test_refunds_cannot_exceed_due`.
  - Fix: Enforced strict validation: `type(amount) is int and amount > 0`. Verified that `status in ("REJECTED", "CANCELLED")` and `payment_status == "PAID"`. Ensured `amount <= (refund_due_paise - refunded_paise)`. Only transitioned `payment_status` to `"REFUNDED"` when `refunded_paise == refund_due_paise`.
- Issue 3: Flawed Order Reconciliation
  - Symptom: Status mismatches were ignored and falsely appended to `matched`. Mismatched amount field names (`total_paise` vs `amount_paise`) produced false amount discrepancies.
  - Hypothesis: Starter reconciliation compared `a.get("amount_paise") != b.get("amount_paise")` without fallback, and had an `else` branch directly appending to `matched` without checking `status`.
  - Evidence: `test_reconciliation_status_mismatch_matrix` failures and incorrect `main.py` output.
  - Fix: Normalized amount extraction via `r.get("amount_paise") if "amount_paise" in r else r.get("total_paise")`. Recorded `amount_mismatches` and `status_mismatches` independently, and only marked an order as `matched` if both amount and status matched.

## 4. Implementation decisions
- Main changes and why:
  - All changes were isolated cleanly inside `service.py`. Kept logic standard and beginner-friendly using basic dictionary operations and guards.
  - Preserved non-mutating functional behavior with `copy.deepcopy(order)`.
- Alternatives considered and why rejected:
  - Class-based state machine: Rejected to preserve original function contracts and keep project structure unchanged.
  - Third-party validation libraries (pydantic/marshmallow): Rejected to avoid unnecessary dependencies and adhere to minimal, standard Python constraints.
- Assumptions:
  - Event IDs are strings or integers. Missing or `None` event IDs do not trigger deduplication blocks.
  - Currency amounts are exclusively represented as non-negative integer paise.

## 5. Verification
- Tests added or changed:
  - Preserved all existing 212 tests in `test_acceptance_matrix.py` and `test_contract.py`.
- Commands run and actual results:
  - `py -m pytest -v`: 212 passed, 0 failed in 0.15s.
  - `py -m main`: Demo reconciled correctly (`ORD-101` matched, `ORD-102` status mismatch, `ORD-103` missing from provider, `ORD-104` missing from internal).
- Edge cases verified:
  - Booleans passed as integers (`True`/`False`), floats (`0.5`), and strings (`"10"`).
  - Cancellation after dispatch (`OUT_FOR_DELIVERY` and `DELIVERED`).
  - Cumulative partial refunds reaching exact total due.
  - Empty inputs and orders missing IDs during reconciliation.
- Remaining failures or known limitations:
  - 0 remaining failures. All requirements and test matrices pass cleanly.
