# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
- Commands run before editing:
  - `python -m pytest -q`
  - `python -m main`
- Initial test result (include the actual summary):
  - `62 failed, 150 passed in 2.61s` out of 212 total tests across `tests/test_acceptance_matrix.py` and `tests/test_contract.py`.
- Demo/output observed:
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  Note that in the untouched demo, `ORD-101` and `ORD-102` were incorrectly classified under `amount_mismatches` because internal records used `total_paise` whereas provider records used `amount_paise`, and status differences were ignored.

## 2. Codebase understanding
- Important files and functions inspected:
  - `service.py`: Contains `apply_order_event` (core event state machine) and `reconcile_orders` (internal vs provider summary reconciliation).
  - `models.py`: Defines `new_order` factory generating standard dictionary shapes for internal orders.
  - `fixtures.py` & `data/records.json`: Synthetic datasets containing standard and anomalous event flows (150 orders, 163 provider records, 219 events).
  - `main.py`: Entry point for local offline execution of order reconciliation.
  - `tests/test_acceptance_matrix.py` & `tests/test_contract.py`: Parametrized and contract test suites defining valid transition matrices, idempotency contracts, refund eligibility/bounds, and reconciliation expectations.
- Order lifecycle or data flow traced:
  - Initial: Order created with status `PLACED`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`.
  - Payment: `payment_confirmed` sets `payment_status="PAID"`.
  - Acceptance: `restaurant_accepted` moves `PLACED -> ACCEPTED`.
  - Rejection: `restaurant_rejected` moves `PLACED -> REJECTED`. If already paid, full order total becomes refundable (`refund_due_paise = total_paise`).
  - Cancellation: `cancel_requested` is valid from `PLACED` or `ACCEPTED` to `CANCELLED`. If paid, sets `refund_due_paise = total_paise`. Cancel requested after `dispatch_started` (`OUT_FOR_DELIVERY` or `DELIVERED`) must be ignored.
  - Dispatch & Delivery: `dispatch_started` transitions `ACCEPTED -> OUT_FOR_DELIVERY`. `order_delivered` transitions `OUT_FOR_DELIVERY -> DELIVERED`.
  - Refund: `refund_processed` applies only to `PAID` cancelled/rejected orders with positive integer paise up to outstanding `refund_due_paise - refunded_paise`. Transitions `payment_status` to `REFUNDED` only when fully refunded.
- How you confirmed your understanding:
  - Cross-referenced the specifications in `STUDENT_PROBLEM_STATEMENT.md` against every failure in the baseline test runner output and inspected `reconciliation_edge_cases` in `data/records.json`.

## 3. Investigation and implementation strategy
- Issue 1: Missing event idempotency
  - Symptom: `test_payment_event_replay_idempotent` and `test_duplicate_event_is_idempotent` failed with duplicate event IDs in `processed_event_ids` (`['e1', 'e1'] == ['e1']`).
  - Hypothesis: `apply_order_event` lacked an early return guard checking if `event_id` was already present in `out["processed_event_ids"]`.
  - Fix: Check `if event_id is not None and event_id in out["processed_event_ids"]: return out` before processing any event logic.
- Issue 2: Lax refund processing validation
  - Symptom: `test_refund_requires_eligible_order`, `test_invalid_refund_amounts_are_ignored`, `test_refunds_cannot_exceed_due` failed. Non-integer amounts (`True`, floats, strings), negative amounts, amounts on unpaid/non-cancelled orders, and amounts exceeding remaining balance were applied.
  - Hypothesis: Starter code blindly added `event.get("amount_paise", 0)` without validating order eligibility (must be `REJECTED`/`CANCELLED` and `PAID`), type (`type(amount) is int and amount > 0`), and upper bound (`already_refunded + amount <= refund_due_paise`).
  - Fix: Implemented strict multi-clause guard enforcing status eligibility, type check, positive value, and non-exceedance of remaining refundable due.
- Issue 3: Reconciliation status mismatches & key mismatch
  - Symptom: `test_reconciliation_status_mismatch_matrix` and `test_reconcile_reports_status_difference` failed because status differences were either skipped or labeled as `matched`. Furthermore, `main.py` failed to match `ORD-101` because internal orders use `total_paise` while provider records use `amount_paise`.
  - Hypothesis: Reconciliation logic lacked checks for status differences and did not normalize the amount key between internal and external records.
  - Fix: Normalized amount lookup using `a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")`, tracked both `amount_mismatch` and `status_mismatch` independently, and populated `status_mismatches` and `amount_mismatches` while only adding strictly identical pairs to `matched`.

## 4. Implementation decisions
- Main changes and why:
  - Used `deepcopy` at function start to maintain immutability of caller inputs (`test_input_order_is_not_mutated`).
  - Checked `type(amount) is int` rather than `isinstance(amount, int)` because in Python `bool` inherits from `int` (`isinstance(True, int)` evaluates to `True`).
  - Preserved list ordering of `processed_event_ids` for deterministic auditability while deduplicating replays.
  - Handled late payment arrival where an order was rejected/cancelled before payment confirmation by ensuring `payment_confirmed` sets `refund_due_paise = total_paise` if unpaid previously.
- Alternatives considered and why rejected:
  - Converting `processed_event_ids` to a Python `set`: Rejected because order of event ingestion would be lost and contract tests expect list structures.
  - Silent clamping of excess refund amounts: Rejected because the problem statement explicitly specifies that invalid refund attempts that exceed balance must be rejected rather than partially rounded.
- Assumptions:
  - Order amounts and refund amounts are non-negative integer paise.
  - Event IDs are strings or None; when None, events are processed without ID deduplication tracking.

## 5. Verification
- Tests added or changed:
  - Preserved 100% of existing tests in `tests/test_acceptance_matrix.py` and `tests/test_contract.py`.
  - Added 9 regression tests in `tests/test_regression.py` covering late payments, dual status/amount reconciliation mismatches, non-integer boolean amounts, and event IDs.
- Commands run and actual results:
  - Baseline: `62 failed, 150 passed in 2.61s`
  - Post-fix: `221 passed in 0.79s`
  - Demo: `python -m main` executes correctly, matching `ORD-101` and accurately flagging status mismatch on `ORD-102`.
- Edge cases verified:
  - Idempotency replays, cancellation after dispatch, boolean/float refund attempts, cumulative refund overflow, dual reconciliation mismatches.
- Remaining failures or known limitations:
  - 0 failures. Clean pass on all suites.