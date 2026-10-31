# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
-ORD-101, total 45900, starts PLACED and UNPAID. Steps 1–4 are the demo events.

| Step | Event | Expected | Actual |
|---|---|---|---|
| 1 | payment_confirmed | PLACED, PAID | PLACED, PAID |
| 2 | restaurant_rejected | REJECTED, due 45900 | REJECTED, due 45900 |
| 3 | refund 20000 (EV-3) | PAID, refunded 20000 | PAID, refunded 20000 |
| 4 | refund 20000 (EV-3 again) | No change | refunded 20000 |
| 5 | refund 25900 (EV-4) | REFUNDED, refunded 45900 | REFUNDED, refunded 45900 |

## 2. Three edge cases
1.Cancel after dispatch
    -Expected: ignored. Actual: OUT_FOR_DELIVERY.
    -Test: test_cancel_after_dispatch_is_ignored
2.Refund 30000 with only 25900 left
    -Expected: ignored. Actual: refunded stays 20000.
    -Test: test_refunds_cannot_exceed_due
3.Payment after cancel
    -Expected: full total due. Actual: PAID, due 1000.
    -Test: test_payment_after_cancellation_creates_refund_due

## 3. Assumptions and limitations
-Cancel only before dispatch (PLACED or ACCEPTED).
-Paid order cancelled or rejected: refund due = total.
-Refunds can't exceed what's left; REFUNDED only when refunded = due.
-Limitations: out-of-order events ignored; no cancellation fees.
