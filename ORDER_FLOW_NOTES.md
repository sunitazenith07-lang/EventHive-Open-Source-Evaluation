# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
-Order ORD-101, total 45900 paise, starting as PLACED and UNPAID.
-Steps 1–4 are the events python -m main runs (fixtures.py). Step 5 finishes the refund.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | payment_confirmed (EV-1) | PLACED, PAID, due 0, refunded 0 | PLACED, PAID, due 0, refunded 0 |
| 2 | restaurant_rejected (EV-2) | REJECTED, PAID, due 45900, refunded 0 | REJECTED, PAID, due 45900, refunded 0 |
| 3 | refund_processed 20000 (EV-3) | Partial refund: REJECTED, still PAID, refunded 20000 | REJECTED, PAID, due 45900, refunded 20000 |
| 4 | refund_processed 20000 (EV-3 again) | Replay ignored: nothing changes | REJECTED, PAID, due 45900, refunded 20000 |
| 5 | refund_processed 25900 (EV-4) | Fully refunded: REJECTED, REFUNDED, refunded 45900 | REJECTED, REFUNDED, due 45900, refunded 45900 |

-processed_event_ids at the end: EV-1, EV-2, EV-3, EV-4. EV-3 is stored once.

## 2. Three edge cases
1.Cancel after dispatch
    -Input: restaurant_accepted, dispatch_started, then cancel_requested.
    -Expected: the cancel is ignored and the order stays OUT_FOR_DELIVERY.
    -Actual: OUT_FOR_DELIVERY.
    -Test: test_cancel_after_dispatch_is_ignored
2.Refund bigger than what's left
    -Input: ORD-101 after step 3 (25900 left), then a refund of 30000.
    -Expected: ignored, because it's more than the outstanding amount.
    -Actual: refunded stays 20000 and payment stays PAID.
    -Test: test_refunds_cannot_exceed_due
3.Payment after cancellation
    -Input: an unpaid order (total 1000) is cancelled, then payment_confirmed arrives.
    -Expected: payment is recorded and the full total becomes due for refund.
    -Actual: CANCELLED, PAID, refund_due 1000.
    -Test: test_payment_after_cancellation_creates_refund_due

## 3. Assumptions and limitations
-Cancellation is allowed only from PLACED or ACCEPTED. After dispatch it's ignored.
-Accept and reject only work on PLACED orders. Dispatch only works on ACCEPTED orders, and delivery only on OUT_FOR_DELIVERY.
-Refund rule: when a paid order is cancelled or rejected (or payment arrives afterwards), refund_due_paise = total_paise.
-A refund must be a positive whole number of paise, on a paid CANCELLED or REJECTED order, and no more than refund_due - refunded.
-Payment becomes REFUNDED only when refunded_paise equals refund_due_paise. Partial refunds stay PAID.
-Every event needs an event_id, and each ID is used once, even if the event changed nothing.
-Limitations: out-of-order events are ignored, not saved; there are no cancellation fees (the refund is always the full total); a DELIVERED order can't be refunded.
