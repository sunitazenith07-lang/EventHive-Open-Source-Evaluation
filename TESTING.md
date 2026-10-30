# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: Python 3.13.15
- Command run: `python -m pytest -q`
- Actual test summary: `225 passed in 0.72s` (Initial baseline: `62 failed, 150 passed in 1.21s`)

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Event replay idempotency: Order `O1` receiving `payment_confirmed` (`event_id="e1"`) twice | Second application is a no-op; state remains `PAID`, `processed_event_ids` contains `["e1"]` exactly once | `processed_event_ids: ["e1"]`, `payment_status: "PAID"` | `tests/test_contract.py::test_duplicate_event_is_idempotent`, `tests/test_regression.py::test_refund_processed_replay_idempotency` |
| 2 | Cancellation attempted after dispatch: Order in `OUT_FOR_DELIVERY` receives `cancel_requested` | Order status must remain `OUT_FOR_DELIVERY`; cancellation is rejected and refund due remains 0 | `status: "OUT_FOR_DELIVERY"`, `refund_due_paise: 0` | `tests/test_contract.py::test_cancel_after_dispatch_is_ignored`, `tests/test_acceptance_matrix.py::test_order_state_transition_matrix[OUT_FOR_DELIVERY-cancel_requested-OUT_FOR_DELIVERY]` |
| 3 | Boolean refund amount rejection: Order `CANCELLED` & `PAID` receives refund with `amount_paise=True` or `False` | Reject refund because boolean is not integer paise; refund credited must be 0 and payment status remains `PAID` | `refunded_paise: 0`, `payment_status: "PAID"` | `tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]`, `tests/test_regression.py::test_boolean_refund_amount_rejected` |
| 4 | Over-refund rejection on cumulative refunds: Order due 5000 paise has 3000 refunded; receives refund of 2500 paise | 2500 exceeds remaining 2000 paise balance; refund is ignored, refunded paise remains 3000 | `refunded_paise: 3000`, `payment_status: "PAID"` | `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due[3000-2000]`, `tests/test_regression.py::test_cumulative_partial_refunds_to_completion_and_overage_rejection` |
| 5 | Simultaneous amount and status mismatch: Internal order has `amount_paise=1000, status="PLACED"`; provider has `amount_paise=1200, status="DELIVERED"` | Order ID must be reported in both `amount_mismatches` and `status_mismatches`, and excluded from `matched` | `amount_mismatches: ["ORD-MIX"]`, `status_mismatches: ["ORD-MIX"]`, `matched: []` | `tests/test_regression.py::test_reconciliation_simultaneous_amount_and_status_mismatch` |
| 6 | Late payment after unpaid cancellation: Order cancelled while `UNPAID` subsequently receives `payment_confirmed` | Order updates `payment_status` to `PAID` and sets `refund_due_paise` to `total_paise` | `payment_status: "PAID"`, `refund_due_paise: 3500` | `tests/test_regression.py::test_late_payment_on_previously_cancelled_order` |
| 7 | Data model field asymmetry: Internal order uses `total_paise=4500` while provider uses `amount_paise=4500` | Reconciliation normalizes amount lookup and reports exact match | `matched: ["ORD-001"]`, `amount_mismatches: []` | `tests/test_regression.py::test_reconciliation_uses_internal_total_paise` |

## Regression tests added
List the defects fixed and the tests added to prevent them from returning.
1. **Idempotency Defect**: Replaying any processed event duplicated IDs and triggered state actions.
   - Regression tests: `tests/test_regression.py::test_refund_processed_replay_idempotency`, `tests/test_regression.py::test_integer_event_ids_and_idempotency`, and 20 parametrized tests in `tests/test_acceptance_matrix.py::test_payment_event_replay_idempotent`.
2. **Unvalidated Refund Defect**: Ineligible orders, non-positive amounts, non-integer amounts (including booleans), and overages were credited.
   - Regression tests: `tests/test_regression.py::test_cumulative_partial_refunds_to_completion_and_overage_rejection`, `tests/test_regression.py::test_boolean_refund_amount_rejected`, `tests/test_regression.py::test_refund_on_ineligible_order_statuses`.
3. **Reconciliation Masking Defect**: Status mismatches were masked as matched if amounts matched; simultaneously mismatched orders dropped status mismatch reporting.
   - Regression tests: `tests/test_regression.py::test_reconciliation_simultaneous_amount_and_status_mismatch`, `tests/test_regression.py::test_reconciliation_uses_internal_total_paise`, `tests/test_regression.py::test_reconciliation_filters_non_dict_and_missing_order_id`.
4. **Input Robustness & Immutability**: Passing `None`, missing keys, or malformed entries corrupted internal dictionary values or mutated caller dictionaries.
   - Regression tests: `tests/test_regression.py::test_defensive_handling_of_malformed_inputs`, `tests/test_regression.py::test_input_immutability_during_event_application`.
5. **Stretch Work Feature**: Verified order state distribution aggregation.
   - Regression test: `tests/test_regression.py::test_summarise_orders_by_state_stretch`.

## Remaining failures or limitations
- Remaining failing tests: **None (0 failures)**. All 225 tests pass.
- Limitations: In-memory dictionary processing assumes datasets fit within system RAM. For distributed streaming pipelines, storage backends (PostgreSQL, Kafka, Redis) should manage event offset tracking and database ACID transaction guarantees.