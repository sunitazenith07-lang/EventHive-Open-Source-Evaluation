# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
List the events in order, the expected state after each event, and the actual state your implementation returns.

| Step | Event           | Expected order/payment/refund state   | Actual result |
|------|-----------------|---------------------------------------|---------------|
| 1 |payment_confirmed   |Order: PLACED, Payment: PAID           |Order: PLACED, Payment: PAID |
| 2 |restaurant_accepted |Order: ACCEPTED, Payment: PAID         |Order: ACCEPTED, Payment: PAID |
| 3 |dispatch_started    |Order: OUT_FOR_DELIVERY, Payment: PAID |Order: OUT_FOR_DELIVERY, Payment: PAID |
| 4 |order_delivered     |Order: DELIVERED, Payment: PAID        |Order: DELIVERED, Payment: PAID |

## 2. Three edge cases
For each, state the input/event sequence, expected behaviour, actual observed result, and test that verifies it.
1. Case: Duplicate payment_confirmed event sent twice.
   - Expected behaviour: The first event marks the order as PAID; the second event is ignored based on event_id.
   - Actual observed result: The order state remained unchanged after the second event.
   - Test: test_contract.py
2. Case: cancel_requested event sent after dispatch_started.
   - Expected behaviour: The order should remain OUT_FOR_DELIVERY because cancellation is not allowed after dispatch.
   - Actual observed result: The order status did not change to CANCELLED.
   - Test: test_acceptance_matrix.py
3. Case: refund_processed event for an amount exceeding refund_due_paise.
   - Expected behaviour: The refund should be rejected, and refunded_paise should not increase.
   - Actual observed result: The refund was ignored; state remained unchanged.
   - Test: test_contract.py

## 3. Assumptions and limitations
Document assumptions about cancellation eligibility, dispatch transitions, refund due/refunded amounts, and any unresolved issue.
Cancellation Eligibility: I assumed that an order can only be cancelled if it is in the PLACED or ACCEPTED state. Once it moves to OUT_FOR_DELIVERY or DELIVERED, it is no longer eligible for cancellation.
Dispatch Transitions: I assumed that dispatch_started can only occur if the restaurant has already accepted the order (ACCEPTED state).

Refund Logic: I assumed that refunds are only applicable to orders that were both paid (PAID) and subsequently CANCELLED or REJECTED.

Money Handling: I assumed all money values are provided in paise (integers) to avoid floating-point precision errors common in financial applications.

Unresolved Issues: No unresolved issues; all required acceptance criteria from the problem statement are met and verified by tests.