# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
List the events in order, the expected state after each event, and the actual state your implementation returns.

| Step | Event | Expected order/payment/refund state |
|---|---|---|---|
| 1 | payment_confirmed | PLACED, PAID |
| 2 | restaurant_accepted | ACCEPTED, PAID |
| 3 | dispatch_started | OUT_FOR_DELIVERY, PAID |
| 4 | order_delivered | DELIVERED, PAID |

## 2. Three edge cases
1. Duplicate event ID: Second event is ignored.
2. Cancellation after dispatch: Order remains OUT_FOR_DELIVERY.
3. Excess refund: Refund exceeding remaining balance is rejected.

## 3. Assumptions and limitations\
- Cancellation alloweed before dispatch.
- Refunds allowed only for eligible paid orders.
- Refund amounts use integer paise.
- Full refund marks payment as REFUNDED.