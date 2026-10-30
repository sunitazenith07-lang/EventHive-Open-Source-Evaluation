# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- **Python version:** Python 3.13.15
- **Command run:** `python -m pytest -q`
- **Actual test summary:** `223 passed in 0.18s`

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Duplicate event ID replay (`event_id="EV-000"`, `type="payment_confirmed"`) | Event is processed once; replaying identical event ID does not duplicate event IDs or re-apply mutation. | `processed_event_ids` remains `['EV-000']`, `payment_status="PAID"`. | `test_acceptance_matrix.py::test_payment_event_replay_idempotent[EV-000]` |
| 2 | Boolean refund amount (`amount_paise=True`) on paid cancelled order | Non-integer/boolean values are strictly ignored; monetary balance remains unmodified. | `refunded_paise == 0`, `payment_status == "PAID"`. | `test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]` |
| 3 | Cancellation requested after dispatch (`status="OUT_FOR_DELIVERY"`, `type="cancel_requested"`) | Transition is rejected; order status remains `OUT_FOR_DELIVERY` without initiating a refund. | `status == "OUT_FOR_DELIVERY"`, `refund_due_paise == 0`. | `tests/test_regression.py::test_cancellation_after_dispatch_is_ignored` |
| 4 | Cumulative refund exceeding outstanding due (Order due 5000 paise; first refund 3000 paise, second refund 2500 paise) | Second refund exceeds outstanding refundable amount (2000 paise remaining); rejected entirely. | `refunded_paise == 3000`, `payment_status == "PAID"`. | `tests/test_regression.py::test_cumulative_refund_exceeding_due_is_rejected` |
| 5 | Simultaneous reconciliation mismatch (Internal: 5000 paise, PLACED; Provider: 6000 paise, CANCELLED) | Order is reported in both `amount_mismatches` and `status_mismatches`, and excluded from `matched`. | `amount_mismatches == ["ORD-BOTH"]`, `status_mismatches == ["ORD-BOTH"]`, `matched == []`. | `tests/test_regression.py::test_reconciliation_simultaneous_amount_and_status_mismatch` |
| 6 | Late payment arrival after order rejection (Order rejected while UNPAID, followed by `payment_confirmed`) | Payment status updates to `PAID` and `refund_due_paise` is automatically set to `total_paise` (1500). | `status == "REJECTED"`, `payment_status == "PAID"`, `refund_due_paise == 1500`. | `tests/test_regression.py::test_late_payment_after_rejection_activates_refund_due` |

## Regression tests added
Defects fixed and the tests added to prevent regressions:
- **`tests/test_regression.py::test_customer_cancels_before_dispatch_paid`**: Protects cancellation of paid orders prior to dispatch, ensuring refund due is properly recorded.
- **`tests/test_regression.py::test_cancellation_after_dispatch_is_ignored`**: Ensures cancellation cannot override `OUT_FOR_DELIVERY` status.
- **`tests/test_regression.py::test_restaurant_rejects_unpaid_order`**: Verifies that rejecting an unpaid order does not create phantom refund due.
- **`tests/test_regression.py::test_restaurant_rejects_paid_order`**: Verifies that rejecting a paid order sets `refund_due_paise` equal to `total_paise`.
- **`tests/test_regression.py::test_late_payment_after_rejection_activates_refund_due`**: Protects handling of out-of-order payment confirmation after rejection.
- **`tests/test_regression.py::test_duplicate_event_idempotency_does_not_double_count`**: Ensures replayed refund events cannot process twice.
- **`tests/test_regression.py::test_partial_refund_then_full_refund_flow`**: Validates multi-step partial refund transitions leading to `REFUNDED` status.
- **`tests/test_regression.py::test_cumulative_refund_exceeding_due_is_rejected`**: Prevents over-refunding beyond due amount.
- **`tests/test_regression.py::test_reconciliation_simultaneous_amount_and_status_mismatch`**: Verifies independent reporting for dual mismatches.
- **`tests/test_regression.py::test_reconciliation_handles_none_and_malformed_records`**: Protects against malformed, null, and non-dict records.
- **`tests/test_regression.py::test_export_awaiting_refund_csv`**: Tests the optional stretch export feature for outstanding refunds.

## Remaining failures or limitations
- **Remaining failures:** None. All 223 tests pass.
- **Limitations:** Processing assumes single-thread in-memory execution. In multi-server production environments, distributed locks or database transactions are recommended for concurrent event streams.
