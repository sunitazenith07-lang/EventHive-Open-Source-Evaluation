# ORDER_FLOW_NOTES.md — Required submission

I've mapped out the order lifecycle by tracing a few different scenarios through the `service.py` logic.

## 1. Example order-event sequence

Here is a typical successful order path from placement to delivery:

| Step | Event           | Expected order/payment/refund state   | Actual result |
|------|-----------------|---------------------------------------|---------------|
| 1 | payment_confirmed   | Order: PLACED, Payment: PAID           | Order: PLACED, Payment: PAID |
| 2 | restaurant_accepted | Order: ACCEPTED, Payment: PAID         | Order: ACCEPTED, Payment: PAID |
| 3 | dispatch_started    | Order: OUT_FOR_DELIVERY, Payment: PAID | Order: OUT_FOR_DELIVERY, Payment: PAID |
| 4 | order_delivered     | Order: DELIVERED, Payment: PAID        | Order: DELIVERED, Payment: PAID |

## 2. Three edge cases

I specifically tested these three scenarios to make sure the system doesn't fail on weird inputs:

1. **Scenario: Duplicate payment_confirmed event**
   - **Input**: Sending the same `payment_confirmed` event twice with the same `event_id`.
   - **Expected**: The first one should set payment to PAID; the second one should be completely ignored.
   - **Result**: It worked—the order state didn't change the second time around.
   - **Verification**: Handled by `test_duplicate_event_is_idempotent` in `test_contract.py`.

2. **Scenario: Late cancellation request**
   - **Input**: Sending `cancel_requested` after the order is already `OUT_FOR_DELIVERY`.
   - **Expected**: The order should stay as `OUT_FOR_DELIVERY` because you can't cancel once it's on the bike.
   - **Result**: The status stayed as `OUT_FOR_DELIVERY` as expected.
   - **Verification**: Verified in `tests/test_contract.py` under `test_cancel_after_dispatch_is_ignored`.

3. **Scenario: Over-refunding the customer**
   - **Input**: A `refund_processed` event with an amount higher than the remaining `refund_due_paise`.
   - **Expected**: The system should block this and not increase the `refunded_paise` total.
   - **Result**: The refund was ignored and the total stayed the same.
   - **Verification**: Checked via `test_refund_cannot_exceed_amount_due` in `test_contract.py`.

## 3. Assumptions and limitations

When implementing this, I made a few key assumptions based on the problem statement:

- **Cancellation**: I've restricted cancellation to only `PLACED` or `ACCEPTED` orders. Once the status hits `OUT_FOR_DELIVERY`, the order is locked.
- **Dispatch**: A restaurant can't start dispatch unless they've already accepted the order.
- **Refunds**: Only orders that were actually PAID and then either CANCELLED or REJECTED get a refund.
- **Precision**: Everything is in integer paise. I avoided using floats entirely to prevent those annoying rounding errors you get with currency.

As for unresolved issues, the current setup works perfectly for the test suite, though in a real app, I'd probably want to move the `processed_event_ids` list to a set for faster lookups.
