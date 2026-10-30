# TESTING.md — Required submission

## Test command and environment
- **Python version:** Python 3.14.7
- **Command run:** `python -m pytest -q`
- **Actual test summary:**
  ```text
  220 passed, 1 warning in 0.21s
  ```
  *(Starter baseline before fixes: 62 failed, 150 passed in 0.84s)*

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replaying identical event with duplicate `event_id` (`EV-000` through `EV-019`) | Must not re-apply mutation or append duplicate event ID | Replay ignored; `processed_event_ids` contains single ID | `test_payment_event_replay_idempotent`, `test_duplicate_event_is_idempotent` |
| 2 | Invalid refund amounts (`True`, `False`, `0`, `-10`, `0.5`, `"10"`, `[]`, `{}`) | Rejected without updating `refunded_paise` or payment status | `refunded_paise == 0`, `payment_status == "PAID"` | `test_invalid_refund_amounts_are_ignored`, `test_refund_rejects_boolean_amounts` |
| 3 | Refund exceeding remaining due amount (due: 5000, attempt: 5001 or cumulative 4000+2000) | Overflow refund rejected; state stays at previous refund total | `refunded_paise == 4000` (overflow ignored), `<= 5000` | `test_refunds_cannot_exceed_due`, `test_multi_step_partial_refund_flow` |
| 4 | Cancellation requested after dispatch or delivery (`OUT_FOR_DELIVERY`, `DELIVERED`) | Ignored; order status unchanged, no refund due generated | Status preserved (`OUT_FOR_DELIVERY` / `DELIVERED`), `refund_due_paise == 0` | `test_cancel_after_dispatch_is_ignored`, `test_cannot_cancel_out_for_delivery_or_delivered` |
| 5 | Order with simultaneous amount mismatch and status mismatch in reconciliation | Recorded in both `amount_mismatches` and `status_mismatches`, excluded from `matched` | Present in both mismatch lists, `matched == []` | `test_reconciliation_dual_mismatch_amount_and_status` |
| 6 | Late payment confirmation on order previously rejected by restaurant or cancelled | Sets `payment_status = "PAID"` and initializes `refund_due_paise = total_paise` | Order eligible for refund; subsequent `refund_processed` succeeds | `test_payment_confirmed_after_rejection_populates_refund_due`, `test_payment_confirmed_after_cancellation_populates_refund_due` |

## Regression tests added
The following tests were implemented in `tests/test_regression.py` to prevent regressions:
1. `test_duplicate_event_with_conflicting_payload_is_ignored`: Verifies idempotency holds even when repeated event IDs contain payload modifications.
2. `test_payment_confirmed_after_rejection_populates_refund_due`: Protects out-of-order payment arrival after restaurant rejection.
3. `test_payment_confirmed_after_cancellation_populates_refund_due`: Protects out-of-order payment arrival after customer cancellation.
4. `test_refund_rejects_boolean_amounts`: Guards against Python's `bool` subclassing behavior in refund calculations.
5. `test_reconciliation_dual_mismatch_amount_and_status`: Ensures dual-mismatches populate both report categories.
6. `test_cannot_cancel_out_for_delivery_or_delivered`: Enforces that post-dispatch orders cannot be cancelled.
7. `test_multi_step_partial_refund_flow`: Validates cumulative partial refunds transitioning to `REFUNDED` only at exact total.
8. `test_reconciliation_handles_malformed_records`: Verifies reconciliation does not crash when encountering `None` or missing `order_id`.

## Remaining failures or limitations
- **Remaining failures:** None. All 220 tests in the test suite pass (0 failures, 0 errors).
- **Known limitations:** The service evaluates events sequentially in memory. In a distributed multi-instance deployment, idempotency deduplication would require an atomic distributed lock or unique database constraint on `event_id`.
