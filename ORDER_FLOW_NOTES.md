# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
Order total: 1000 paise. This sequence was run through `apply_order_event`.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` (`P1`) | `PLACED`, `PAID`, due 0, refunded 0 | `PLACED`, `PAID`, due 0, refunded 0 |
| 2 | `restaurant_accepted` (`A1`) | `ACCEPTED`, `PAID`, due 0, refunded 0 | `ACCEPTED`, `PAID`, due 0, refunded 0 |
| 3 | `cancel_requested` (`C1`) | `CANCELLED`, `PAID`, due 1000, refunded 0 | `CANCELLED`, `PAID`, due 1000, refunded 0 |
| 4 | `refund_processed` (`R1`, 1000 paise) | `CANCELLED`, `REFUNDED`, due 1000, refunded 1000 | `CANCELLED`, `REFUNDED`, due 1000, refunded 1000 |

## 2. Three edge cases
1. **Cancellation after dispatch:** An order in `OUT_FOR_DELIVERY` remains in that state after `cancel_requested`. Verified by `test_cancel_after_dispatch_is_ignored` and the transition matrix.
2. **Duplicate partial refund:** Replaying the same event ID does not increase a 400-paise refund to 800 paise. Verified by `test_duplicate_refund_event_is_idempotent`.
3. **Refund exceeds the remaining amount:** A refund request larger than the due balance is ignored; accumulated refunds never exceed the due amount. Verified by `test_refund_cannot_exceed_amount_due` and `test_refunds_cannot_exceed_due`.

## 3. Assumptions and limitations
- Cancellation is allowed only from `PLACED` or `ACCEPTED`; dispatch and delivery transitions follow the existing state machine.
- Rejection or cancellation of a paid order sets refund due to the full positive integer order total.
- Refunds apply only to paid cancelled/rejected orders. Partial refunds remain `PAID`; payment changes to `REFUNDED` only when the full due amount has been processed.
- Payment confirmed after cancellation or rejection sets the full order total as due.
- Duplicate order IDs in reconciliation input are not diagnosed; the last row for that ID is used.
