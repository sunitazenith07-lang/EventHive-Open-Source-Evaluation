# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
Starting order: `new_order("ORD-500", 6000)` (status: `PLACED`, payment: `UNPAID`, refund due: 0, refunded: 0).

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `{"event_id": "e1", "type": "payment_confirmed"}` | Payment status becomes `PAID`. Order stays `PLACED`. | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0` |
| 2 | `{"event_id": "e2", "type": "restaurant_accepted"}` | Order status becomes `ACCEPTED`. Payment stays `PAID`. | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0` |
| 3 | `{"event_id": "e3", "type": "cancel_requested"}` | Order status becomes `CANCELLED`. Full amount is marked due (`refund_due_paise=6000`). | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=6000`, `refunded_paise=0` |
| 4 | `{"event_id": "e4", "type": "refund_processed", "amount_paise": 3000}` | First partial refund of 3000. Payment stays `PAID` because 3000 is still due. | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=6000`, `refunded_paise=3000` |
| 5 | `{"event_id": "e5", "type": "refund_processed", "amount_paise": 3000}` | Second refund of 3000. Full 6000 is refunded, payment status becomes `REFUNDED`. | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=6000`, `refunded_paise=6000` |

## 2. Three edge cases

1. **Cancel after dispatch:**
   - Order is in `OUT_FOR_DELIVERY` and a `cancel_requested` event comes in.
   - Expected: Cancellation is ignored. Status stays `OUT_FOR_DELIVERY` and no refund is set.
   - Actual: Status stayed `OUT_FOR_DELIVERY`, `refund_due_paise=0`.
   - Verified by: `test_cancel_after_dispatch_is_ignored`.

2. **Payment arrives after restaurant rejection:**
   - Order was unpaid and rejected (`REJECTED`). Then `payment_confirmed` arrives late.
   - Expected: Payment status updates to `PAID` and `refund_due_paise` is set to the order total so customer gets refunded.
   - Actual: `payment_status="PAID"`, `refund_due_paise=4500`.
   - Verified by: `test_payment_confirmed_after_rejection_sets_refund_due`.

3. **Refund exceeds remaining balance:**
   - Order total is 5000, 3000 was already refunded (2000 remaining). A refund of 2500 comes in.
   - Expected: 2500 is bigger than the remaining 2000, so the refund is ignored completely.
   - Actual: Refund was ignored, `refunded_paise` stayed 3000.
   - Verified by: `test_refunds_cannot_exceed_due`.

## 3. Assumptions and limitations
- Amounts are in integer paise (1 INR = 100 paise).
- Cancellation is only allowed before dispatch (`PLACED` or `ACCEPTED`).
- Refunds only apply to paid orders that are `CANCELLED` or `REJECTED`.
- Reconciliation handles both `total_paise` and `amount_paise` keys.
