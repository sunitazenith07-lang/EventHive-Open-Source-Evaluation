# ORDER_FLOW_NOTES.md - Order flow results

AI assistance was used in the implementation and test work. Confirm evaluation policy before submission.

## 1. Example order-event sequence
Verified by `test_paid_rejection_partial_then_full_refund_flow` with a 1000-paise order.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` (`e1`) | PLACED / PAID / due 0 / refunded 0 | PLACED / PAID / 0 / 0 |
| 2 | `restaurant_rejected` (`e2`) | REJECTED / PAID / due 1000 / refunded 0 | REJECTED / PAID / 1000 / 0 |
| 3 | `refund_processed` (`r1`, 400) | REJECTED / PAID / due 1000 / refunded 400 | REJECTED / PAID / 1000 / 400 |
| 4 | `refund_processed` (`r2`, 600) | REJECTED / REFUNDED / due 1000 / refunded 1000 | REJECTED / REFUNDED / 1000 / 1000 |

## 2. Three edge cases
1. Replay `r1`: remains 400 refunded; verified by `test_duplicate_refund_event_is_idempotent`.
2. Cancel an `OUT_FOR_DELIVERY` order: status remains unchanged; verified by `test_cancel_after_dispatch_is_ignored`.
3. Internal/provider amount and status both differ: both mismatch arrays contain the ID and `matched` is empty; verified by `test_reconcile_reports_amount_and_status_differences_separately`.

## 3. Assumptions and limitations
- Refunds apply only to paid rejected/cancelled orders with positive outstanding due.
- Only positive integer paise are accepted, and a refund cannot exceed due minus already refunded.
- Payment becomes REFUNDED only when refunded equals due.
- Duplicate summary IDs are not resolved explicitly; current dictionary construction keeps the last row.
