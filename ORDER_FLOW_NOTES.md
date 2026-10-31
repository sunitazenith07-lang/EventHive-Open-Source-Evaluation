# ORDER_FLOW_NOTES.md

## 1. Example order-event sequence

Example: Order amount = 1000 paise.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | Order created | PENDING / UNPAID / Refund = 0 | PENDING / UNPAID / 0 |
| 2 | Payment confirmed | PENDING / PAID / Refund = 0 | PENDING / PAID / 0 |
| 3 | Order rejected | REJECTED / PAID / Refund due = 1000 | REJECTED / PAID / 0 refunded |
| 4 | Refund of 1000 | REJECTED / REFUNDED / Refund = 1000 | REJECTED / REFUNDED / 1000 |

## 2. Three edge cases

1. **Duplicate event ID**
   - Input: Send the same event twice.
   - Expected: The second event should be ignored.
   - Actual: Duplicate event is ignored.
   - Test: Duplicate event test.

2. **Invalid refund amount**
   - Input: Refund amount is 0, negative, decimal, or invalid type.
   - Expected: Refund should not be processed.
   - Actual: Invalid refund is ignored.
   - Test: Invalid refund amount tests.

3. **Refund more than due**
   - Input: Refund amount is greater than the refund due.
   - Expected: Refund should be ignored.
   - Actual: Refund is not added.
   - Test: Refund limit test.

## 3. Assumptions and limitations

- Refund is allowed only for REJECTED or CANCELLED orders.
- Payment must be PAID before a refund.
- Refund amount must be a positive integer.
- Total refunded amount cannot be greater than refund due.
- Order status and payment status both need to match during reconciliation.
- I kept the existing code structure and added basic validation checks.
- Performance was not benchmarked, so no speed improvement is claimed.