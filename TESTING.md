# TESTING.md — Required submission

This document records the empirical testing process, environment details, edge-case validations, and regression suite added to verify the OrderOps service.

## Test command and environment
- **Python version:** Python 3.13.15
- **Commands run:**
  - `python -m pytest -q`
  - `python -m main`
- **Initial baseline test summary:** `62 failed, 150 passed in 0.60s` (212 total tests)
- **Final test summary:** `219 passed in 0.27s` (212 visible tests + 7 custom regression tests)

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | **Replayed Payment Event**<br>`order` with `processed_event_ids=["EV-001"]`, re-receiving event `EV-001` (`payment_confirmed`) | Idempotent short-circuit: do not change state, do not append duplicate ID to `processed_event_ids`. | `processed_event_ids` remains `["EV-001"]`, state untouched. | `test_payment_event_replay_idempotent[EV-001]` & `test_duplicate_event_is_idempotent` |
| 2 | **Late Payment Confirmation after Rejection**<br>Order rejected when `payment_status="UNPAID"`, then late `payment_confirmed` webhook arrives. | Order remains `REJECTED`, `payment_status` becomes `PAID`, `refund_due_paise` updated to `total_paise` (4500) to allow refunding. | `status="REJECTED"`, `payment_status="PAID"`, `refund_due_paise=4500`. | `tests/test_regression_edge_cases.py::test_edge_case_late_payment_after_restaurant_rejection` |
| 3 | **Boolean Refund Amount (`amount_paise=True`)**<br>Order `CANCELLED`, `PAID`, receiving refund event with `amount_paise=True` | In Python `isinstance(True, int)` is `True`. Must reject boolean amounts and not refund 1 paise. | `refunded_paise` remains `0`, `payment_status="PAID"`. | `test_invalid_refund_amounts_are_ignored[True]` & `test_edge_case_boolean_amount_in_refund_ignored` |
| 4 | **Refund Exceeding Outstanding Balance**<br>Order `CANCELLED`, `PAID`, `refund_due_paise=5000`, receiving `refund_processed` with `amount_paise=6000` | Exceeds due balance; must reject refund completely. | `refunded_paise` remains `0`, `payment_status="PAID"`. | `test_refunds_cannot_exceed_due[5000-1]` & `test_refund_cannot_exceed_amount_due` |
| 5 | **Cancellation Attempt After Dispatch (`OUT_FOR_DELIVERY`)**<br>Order in `OUT_FOR_DELIVERY` receiving `cancel_requested` | Food already picked up; cancellation must be ignored, state remains `OUT_FOR_DELIVERY`. | Order remains `OUT_FOR_DELIVERY`, `refund_due_paise=0`. | `test_cancel_after_dispatch_is_ignored` & `test_edge_case_cancellation_after_dispatch_and_delivered_ignored` |
| 6 | **Sequential Partial Refunds Reaching Full Amount**<br>Due 5000 paise; event 1: 2000 paise; event 2: 3000 paise. | After event 1, `refunded_paise=2000`, `payment_status="PAID"` (remains partial). After event 2, `refunded_paise=5000`, `payment_status="REFUNDED"`. | Exact state transition: `PAID` -> `REFUNDED` only when 100% settled. | `test_valid_partial_and_full_refunds` & `test_edge_case_multi_step_partial_refunds_and_over_refund` |
| 7 | **Simultaneous Amount and Status Reconciliation Mismatch**<br>Internal order: `5000 paise, PLACED`. Provider order: `7000 paise, DELIVERED`. | Flagged in both `amount_mismatches` and `status_mismatches`; excluded from `matched`. | Included in both mismatch lists; `matched=[]`. | `tests/test_regression_edge_cases.py::test_edge_case_reconcile_simultaneous_amount_and_status_mismatch` |

## Regression tests added
The following tests were created in `tests/test_regression_edge_cases.py` to prevent regressions:
1. `test_edge_case_late_payment_after_restaurant_rejection`: Verifies late payment confirmation on rejected orders marks `refund_due_paise` properly.
2. `test_edge_case_late_payment_after_cancellation`: Verifies late payment confirmation on cancelled orders marks `refund_due_paise`.
3. `test_edge_case_boolean_amount_in_refund_ignored`: Verifies Python boolean subclass trap (`True`/`False`) does not mutate paise.
4. `test_edge_case_multi_step_partial_refunds_and_over_refund`: Validates multi-step partial refunds and asserts over-refunding is blocked.
5. `test_edge_case_cancellation_after_dispatch_and_delivered_ignored`: Protects dispatched and delivered orders from customer cancellation.
6. `test_edge_case_reconcile_simultaneous_amount_and_status_mismatch`: Tests independent reporting when both amount and status differ.
7. `test_edge_case_malformed_and_none_events`: Ensures system resilience against `None`, empty dictionaries, or unexpected event types without raising exceptions.

## Remaining failures or limitations
- **Remaining test failures:** None (`0 failed, 219 passed`).
- **Architectural limitations:** State and idempotency tracking are maintained in-memory per dictionary record. In a distributed multi-instance production environment, idempotency locks (e.g., Redis SETNX or database unique transaction constraints) and distributed transactions would be required for concurrency.
