# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence

Here is an example of an order (`ORD-9001` for ₹450 = 45000 paise) going through a full lifecycle: paid, accepted, customer-cancelled, and refunded in two parts.

| Step | Event | Expected state | Actual result returned |
|---|---|---|---|
| 1 | `payment_confirmed` (EV-01) | Status: PLACED<br>Payment: PAID<br>Refund due: 0, Refunded: 0 | Status: PLACED, Payment: PAID, Refund due: 0, Refunded: 0. Event EV-01 recorded. |
| 2 | `restaurant_accepted` (EV-02) | Status: ACCEPTED<br>Payment: PAID<br>Refund due: 0, Refunded: 0 | Status: ACCEPTED, Payment: PAID. Event EV-02 recorded. |
| 3 | `cancel_requested` (EV-03) | Status: CANCELLED<br>Payment: PAID<br>Refund due: 45000 paise, Refunded: 0 | Status: CANCELLED, Payment: PAID, Refund due: 45000 paise. Customer is now owed full refund. |
| 4 | `refund_processed` (EV-04, 20000 paise) | Status: CANCELLED<br>Payment: PAID (partial refund)<br>Refund due: 45000, Refunded: 20000 | Status: CANCELLED, Payment: PAID, Refunded: 20000 paise. Stays in PAID because 25000 paise is still owed. |
| 5 | `refund_processed` (EV-05, 25000 paise) | Status: CANCELLED<br>Payment: REFUNDED (complete)<br>Refund due: 45000, Refunded: 45000 | Status: CANCELLED, Payment: REFUNDED, Refunded: 45000 paise. Full amount returned, so status flips to REFUNDED. |

## 2. Three edge cases

### 1. Customer tries to cancel after the food has been dispatched
- **Scenario:** The order has moved to `OUT_FOR_DELIVERY` (the delivery partner already picked it up). The customer sends a `cancel_requested` event.
- **What should happen:** Since the restaurant prepared the food and the rider is on the road, cancellation must be blocked. The order must stay in `OUT_FOR_DELIVERY`, and no refund should be queued.
- **What actually happened:** The system ignored the cancel event. Status stayed `OUT_FOR_DELIVERY`, and `refund_due_paise` stayed 0.
- **Test:** `test_cancel_after_dispatch_is_ignored` and `test_edge_case_cancellation_after_dispatch_and_delivered_ignored`.

### 2. Payment confirmation arrives late after the restaurant already rejected
- **Scenario:** The customer places an order, and the restaurant rejects it quickly (`restaurant_rejected`) while the payment gateway is still processing (`payment_status="UNPAID"`). A few seconds later, the payment goes through and `payment_confirmed` arrives.
- **What should happen:** The order should stay `REJECTED`, payment should mark as `PAID`, and `refund_due_paise` should immediately update to the full order amount so the customer gets their money back.
- **What actually happened:** Status stayed `REJECTED`, payment changed to `PAID`, and `refund_due_paise` was set to `total_paise`.
- **Test:** `tests/test_regression_edge_cases.py::test_edge_case_late_payment_after_restaurant_rejection`.

### 3. Webhook sends the exact same event twice (Duplicate/Replay)
- **Scenario:** Due to a network retry from the payment gateway, the exact same `payment_confirmed` event with `event_id="EV-001"` arrives twice.
- **What should happen:** The first event marks payment as `PAID` and adds the event ID to history. The second event is recognized as already processed and ignored completely, without duplicating the ID in history (`['EV-001']`, not `['EV-001', 'EV-001']`).
- **What actually happened:** The function saw the ID in `processed_event_ids`, returned the order immediately, and left the list with only one entry.
- **Test:** `test_duplicate_event_is_idempotent` and `test_payment_event_replay_idempotent`.

## 3. Assumptions and limitations

### Assumptions:
1. **Money is in integer paise:** We always work in paise (₹1 = 100 paise) so we don't run into float rounding errors (like `0.1 + 0.2 != 0.3`).
2. **Cancellation window:** Customers can only cancel when the order is in `PLACED` or `ACCEPTED`. Once it reaches `OUT_FOR_DELIVERY` or `DELIVERED`, cancellation is blocked.
3. **Refund eligibility:** An order is only eligible for a refund if it is `CANCELLED` or `REJECTED`, the payment was actually received (`PAID`), and `refund_due_paise` is greater than 0.
4. **Partial vs Full refund:** If an order has a partial refund, `payment_status` stays `PAID`. It only changes to `REFUNDED` when the total refunded equals the total amount owed.

### Limitations:
1. **In-memory state:** Orders and event histories are kept in Python dictionaries in memory. If the application stops or restarts, the state is lost.
2. **Concurrency in production:** If two webhooks for the same order hit two different servers at the exact same millisecond, an in-memory list cannot stop a race condition. In production, we would use a database transaction or a distributed lock (like Redis) keyed on `order_id + event_id` to guarantee safety.
