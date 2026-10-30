# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
Order initialized as `new_order("ORD-901", 50000)` (₹500.00).

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` (`EV-01`) | `status`: PLACED, `payment_status`: PAID, `refund_due_paise`: 0 | `status`: PLACED, `payment_status`: PAID, `refund_due_paise`: 0 |
| 2 | `restaurant_accepted` (`EV-02`) | `status`: ACCEPTED, `payment_status`: PAID, `refund_due_paise`: 0 | `status`: ACCEPTED, `payment_status`: PAID, `refund_due_paise`: 0 |
| 3 | `cancel_requested` (`EV-03`) | `status`: CANCELLED, `payment_status`: PAID, `refund_due_paise`: 50000 | `status`: CANCELLED, `payment_status`: PAID, `refund_due_paise`: 50000 |
| 4 | `refund_processed` (`EV-04`, 20000) | `status`: CANCELLED, `payment_status`: PAID, `refunded_paise`: 20000 | `status`: CANCELLED, `payment_status`: PAID, `refunded_paise`: 20000 |
| 5 | `refund_processed` (`EV-05`, 30000) | `status`: CANCELLED, `payment_status`: REFUNDED, `refunded_paise`: 50000 | `status`: CANCELLED, `payment_status`: REFUNDED, `refunded_paise`: 50000 |

## 2. Three edge cases
1. **Cancellation After Dispatch:**
   - *Input:* Order in `OUT_FOR_DELIVERY` receives `cancel_requested`.
   - *Expected:* Order remains `OUT_FOR_DELIVERY`; cancellation is rejected.
   - *Actual:* Status remains `OUT_FOR_DELIVERY`.
   - *Test:* `test_cancel_after_dispatch_is_ignored`.
2. **Duplicate Event Idempotency:**
   - *Input:* Order receives `payment_confirmed` with `event_id="EV-PAY-1"` twice.
   - *Expected:* Payment status set to `PAID` on first call; second call returns order unmodified with single event ID in `processed_event_ids`.
   - *Actual:* `processed_event_ids` contains `["EV-PAY-1"]`.
   - *Test:* `test_duplicate_event_is_idempotent`.
3. **Cumulative Refund Exceeding Due Amount:**
   - *Input:* Cancelled paid order with `refund_due_paise=5000` receives a partial refund of 4000, then a second refund of 2000.
   - *Expected:* First refund is accepted (`refunded_paise=4000`); second refund is rejected because 4000 + 2000 > 5000.
   - *Actual:* `refunded_paise` remains 4000; payment status remains `PAID`.
   - *Test:* `test_refunds_cannot_exceed_due`.

## 3. Assumptions and limitations
- **Currency representation:** All monetary transactions use non-negative integer paise to prevent floating-point rounding errors.
- **Cancellation eligibility:** An order can only be cancelled before dispatch (i.e. in `PLACED` or `ACCEPTED` status). Once `OUT_FOR_DELIVERY` or `DELIVERED`, customer cancellation is disallowed.
- **Refund triggers:** Refunds are due only if an order was paid (`PAID`) and then rejected by the restaurant or cancelled before dispatch.
- **Idempotency scope:** Handled in-memory per order entity using `processed_event_ids`.
