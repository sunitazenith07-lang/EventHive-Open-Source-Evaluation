# TESTING.md — Required Submission

## Test command and environment
- **Python version**: Python 3.13.14 (win32)
- **Command run**: `python -m pytest -v`
- **Actual test summary**: `220 passed in 0.42s` (100% passing across all 3 test suites: `test_acceptance_matrix.py`, `test_contract.py`, and `test_regression.py`).

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replaying identical event: `EVT-100` (`payment_confirmed`) applied twice to new order | Event ID recorded once; payment status set to `PAID` without duplicate append or re-execution | `processed_event_ids: ["EVT-100"]`, `payment_status: "PAID"` | `tests/test_regression.py::test_duplicate_event_idempotency_preserves_single_record` |
| 2 | Boolean amount in refund: `amount_paise = True` or `False` | Rejected as invalid amount; `refunded_paise` remains 0 and `payment_status` stays `PAID` | `refunded_paise: 0`, `payment_status: "PAID"` | `tests/test_regression.py::test_refund_rejection_for_boolean_amount` |
| 3 | Cumulative partial refunds with excess attempt: 3,000 paise due; refund 1,000, attempt 2,500 excess, refund 1,200, refund 800, attempt post-completion 100 | Excess attempt (2,500) ignored; intermediate refunds accumulate to 2,200; final 800 flips status to `REFUNDED`; post-completion refund rejected | Intermediate: 1,000 -> 1,000 (rejected) -> 2,200 -> 3,000 (`REFUNDED`) -> 3,000 (rejected) | `tests/test_regression.py::test_cumulative_partial_refunds_transition_to_refunded_on_exact_completion` |
| 4 | Late payment after cancellation/rejection: order cancelled while `UNPAID`, then `payment_confirmed` arrives | Payment marked `PAID` and `refund_due_paise` correctly populated with `total_paise` | `payment_status: "PAID"`, `refund_due_paise: 4500` | `tests/test_regression.py::test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due` |
| 5 | Cancellation attempted after dispatch: order in `OUT_FOR_DELIVERY` receives `cancel_requested` | State transition disallowed; order status preserved as `OUT_FOR_DELIVERY` | `status: "OUT_FOR_DELIVERY"` | `tests/test_regression.py::test_cancellation_after_dispatch_and_delivery_is_strictly_ignored` |
| 6 | Simultaneous amount and status mismatch: order with amount 1000 vs 1200 and status `PLACED` vs `DELIVERED` | Order included in both `amount_mismatches` and `status_mismatches`; excluded from `matched` | `amount_mismatches: ["ORD-DUAL"]`, `status_mismatches: ["ORD-DUAL"]`, `matched: []` | `tests/test_regression.py::test_reconciliation_detects_simultaneous_amount_and_status_mismatch` |
| 7 | Malformed / non-dict records in reconciliation: `None`, string entries, and dicts without `order_id` | Invalid rows safely skipped without crashing or halting reconciliation of valid orders | Valid order matched deterministically; zero runtime errors | `tests/test_regression.py::test_reconciliation_with_total_paise_and_malformed_entries` |

## Regression tests added
1. **Event Idempotency**: Fixed duplicate event ID appending and re-execution. Protected by `test_duplicate_event_idempotency_preserves_single_record` and 20 parametrized cases in `test_acceptance_matrix.py`.
2. **Boolean Amount Handling**: Fixed boolean type coercion bug in refund validation. Protected by `test_refund_rejection_for_boolean_amount`.
3. **Cumulative Refund Bounds & State Progression**: Fixed refund balance arithmetic, excess refund rejection, and strict transition to `REFUNDED`. Protected by `test_cumulative_partial_refunds_transition_to_refunded_on_exact_completion`.
4. **Late Payment Confirmation**: Fixed zero `refund_due_paise` on paid cancellations/rejections when payment event arrives late. Protected by `test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due`.
5. **Post-Dispatch Cancellation Guard**: Fixed potential cancellation leakage after dispatch. Protected by `test_cancellation_after_dispatch_and_delivery_is_strictly_ignored`.
6. **Reconciliation Status and Schema Normalization**: Fixed status mismatch omission and `total_paise` vs `amount_paise` mapping. Protected by `test_reconciliation_detects_simultaneous_amount_and_status_mismatch` and `test_reconciliation_with_total_paise_and_malformed_entries`.

## Remaining failures or limitations
- **Remaining failures**: None (0 failed, 220 passed).
- **Known limitations**:
  - Processing is synchronous and operates on in-memory dictionary data structures.
  - While late payments after cancellation are supported, out-of-order refunds arriving *before* payment confirmation are rejected as unpaid (a durable dead-letter queue or event resequencer would be recommended in distributed production).
