# Order Flow Notes

## Example order

For this example, I am using an order with a total value of 5,000 paise.

The order starts in the PLACED state, and the payment has not yet been confirmed.

### Event sequence

| Step | Event | Order Status | Payment Status | Refund Due | Refunded |
|---|---|---|---|---:|---:|
| 1 | Order created | PLACED | UNPAID | 0 | 0 |
| 2 | payment_confirmed | PLACED | PAID | 0 | 0 |
| 3 | restaurant_rejected | REJECTED | PAID | 5,000 | 0 |
| 4 | refund_processed (2,000) | REJECTED | PAID | 5,000 | 2,000 |
| 5 | Duplicate refund event | REJECTED | PAID | 5,000 | 2,000 |
| 6 | refund_processed (3,000) | REJECTED | REFUNDED | 5,000 | 5,000 |

The restaurant rejection makes the full order amount refundable because the customer has already paid.

The first refund is only a partial refund, so the payment status remains PAID. When the duplicate notification arrives with the same event ID, it is ignored.

The final refund uses a different event ID and completes the outstanding balance. The order remains REJECTED because processing a refund should not change its delivery history.

## Important observations

### 1. Order status and payment status are separate

A cancelled or rejected order can still have a PAID payment status when its refund is pending.

The two statuses represent different things, so they should not be combined into one field.

### 2. Refunds are cumulative

The refunded amount increases only when a valid refund event is accepted.

The amount already refunded must never exceed the total refund due.

### 3. Event IDs matter

Each event has an identifier. Replaying an event that has already been processed should not apply its effect again.

## Additional edge cases

### Edge case 1: Cancellation after dispatch

If an order is already OUT_FOR_DELIVERY, a cancel_requested event must not change its status to CANCELLED.

### Edge case 2: Partial refund

If the refund due is 5,000 paise and only 2,000 paise has been refunded, the payment status must remain PAID. It becomes REFUNDED only when the full 5,000 paise has been refunded.

### Edge case 3: Late payment confirmation

An order can be cancelled before a delayed payment confirmation arrives. When that payment confirmation is subsequently processed, the order should remain CANCELLED, but the full refund obligation must be established.

## Conclusion

The main thing I learned from following this flow is that order state, payment state and refund accounting need to be handled separately.

Keeping these values independent makes it easier to handle cancellations, delayed notifications and partial refunds without losing track of the actual order history.