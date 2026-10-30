# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | payment_confirmed | status PLACED, payment PAID, refund_due 0, refunded 0 | status PLACED, payment PAID, refund_due 0, refunded 0 |
| 2 | restaurant_rejected | status REJECTED, payment PAID, refund_due total, refunded 0 | status REJECTED, payment PAID, refund_due total, refunded 0 |
| 3 | refund_processed amount 400 | status REJECTED, payment PAID, refunded 400, still partial | status REJECTED, payment PAID, refunded 400 |
| 4 | refund_processed amount remaining due | status REJECTED, payment REFUNDED, refunded full due | status REJECTED, payment REFUNDED, refunded full due |

## 2. Three edge cases
1. Duplicate payment event: replaying payment_confirmed with the same event_id leaves payment PAID and does not append the ID again.
2. Cancellation after dispatch: a cancel_requested event on an OUT_FOR_DELIVERY order leaves it OUT_FOR_DELIVERY.
3. Over-limit refund: a refund larger than the outstanding due is ignored, leaving refunded_paise unchanged.

## 3. Assumptions and limitations
- Cancellation is allowed only from PLACED or ACCEPTED; later cancellation attempts are ignored.
- Refunds apply only to REJECTED or CANCELLED orders with PAID payment status.
- Refund amounts must be positive integers in paise and cannot exceed the outstanding due.
- Payment becomes REFUNDED only when refunded_paise reaches refund_due_paise.
- Duplicate order IDs in reconciliation collapse to the first occurrence.
- Events without event_id are not deduplicated.
