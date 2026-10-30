# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: Python 3.14.6 (Local environment) / Python 3.11 (CI environment)
- Command run: `py -m pytest -v` and `py -m main`
- Actual test summary: `212 passed, 1 warning in 0.15s`

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Boolean refund amounts: `amount_paise = True` or `False` | Reject non-integer paise; keep `refunded_paise = 0` | Ignored, `refunded_paise` stayed `0`, `payment_status` stayed `"PAID"` | `test_invalid_refund_amounts_are_ignored[True]`, `[False]` |
| 2 | Excessive refund exceeding balance: `amount_paise = 5001` on order with `refund_due_paise = 5000` | Exceeds outstanding due; reject transaction | Ignored, `refunded_paise` stayed `0`, no over-refund occurred | `test_invalid_refund_amounts_are_ignored[5001]`, `test_refunds_cannot_exceed_due` |
| 3 | Duplicate event replay: replaying `event_id="EV-000"` with `type="payment_confirmed"` | Idempotency; no duplicate state changes or duplicate entries in `processed_event_ids` | `processed_event_ids` has `['EV-000']` exactly once; state remains intact | `test_payment_event_replay_idempotent[EV-000]` |
| 4 | Cancellation after dispatch: `cancel_requested` on order with status `"OUT_FOR_DELIVERY"` | Ineligible cancellation after dispatch; order must remain in current state | Order status remains `"OUT_FOR_DELIVERY"` | `test_order_state_transition_matrix[OUT_FOR_DELIVERY-cancel_requested-OUT_FOR_DELIVERY]` |
| 5 | Dual mismatch in reconciliation: Order has both different amount and different status between internal and provider | Separately report order ID in both `amount_mismatches` and `status_mismatches`, exclude from `matched` | Order ID correctly added to both mismatch lists, `matched` list is empty | `test_reconciliation_status_mismatch_matrix`, `test_reconciliation_amount_mismatch_matrix` |
| 6 | Ineligible order refund: `refund_processed` applied to order with status `"PLACED"` and `payment_status="UNPAID"` | Reject refund attempt on unconfirmed/unpaid orders | `refunded_paise` stayed `0`, `payment_status` remained `"UNPAID"` | `test_refund_eligibility_matrix[PLACED-UNPAID-0]` |

## Regression tests added
List the defects fixed and the tests added to prevent them from returning.
- **Idempotency Protection**: Validated by `test_payment_event_replay_idempotent` across 20 distinct event IDs and `test_duplicate_event_is_idempotent` in `test_contract.py`.
- **Refund Type and Bounds Checking**: Validated by `test_invalid_refund_amounts_are_ignored` (covering floats, booleans, negative integers, string inputs, None, and lists) and `test_refunds_cannot_exceed_due` across 20 distinct boundary values.
- **Order State Eligibility Matrix**: Validated by `test_refund_eligibility_matrix` across all 12 combinations of order status and payment status.
- **Reconciliation Accuracy**: Validated by `test_reconciliation_status_mismatch_matrix` (12 status variations), `test_reconciliation_amount_mismatch_matrix` (20 amount variations), and deterministic sorting tests.

## Remaining failures or limitations
- Remaining failures: **0**. All 212 tests pass successfully.
- Known limitations: In-flight out-of-order refund events arriving before payment or cancellation are rejected rather than buffered for delayed evaluation.
