# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence

Example synthetic order:
- Order ID: ORD-201
- Initial order status: PLACED
- Total amount: 5000 paise
- Initial payment status: UNPAID

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` | PLACED / PAID / Refund due 0 | PLACED / PAID / Refund due 0 |
| 2 | `restaurant_accepted` | ACCEPTED / PAID / Refund due 0 | ACCEPTED / PAID / Refund due 0 |
| 3 | `dispatch_started` | OUT_FOR_DELIVERY / PAID / Refund due 0 | OUT_FOR_DELIVERY / PAID / Refund due 0 |
| 4 | `order_delivered` | DELIVERED / PAID / Refund due 0 | DELIVERED / PAID / Refund due 0 |

This sequence describes the transitions implemented in `apply_order_event()`.

## 2. Three edge cases

### 1. Partial refund

- Input: A cancelled order with payment status `PAID`, refund due 5000 paise, and a refund event of 2000 paise.
- Expected behaviour: Refunded amount becomes 2000 paise. Payment status remains `PAID`.
- Actual result: The implementation keeps the status `PAID` after a partial refund.
- Test evidence: `test_valid_partial_and_full_refunds` and `test_partial_refund_is_not_marked_complete`.

### 2. Multiple refunds reaching the full amount

- Input: A cancelled order with refund due 5000 paise. Process two refund events of 2500 paise each.
- Expected behaviour: The accumulated refunded amount becomes 5000 paise and payment status becomes `REFUNDED`.
- Actual result: The implementation accumulates valid refunds and marks the payment `REFUNDED` when the full amount is reached.
- Test evidence: `test_refunds_cannot_exceed_due[2500-2500]`.

### 3. Refund amount exceeding the remaining due

- Input: A cancelled order with refund due 5000 paise. Process a refund of 4000 paise followed by another refund of 2000 paise.
- Expected behaviour: The second refund must not be processed because it exceeds the remaining 1000 paise.
- Actual result: The implementation rejects the second refund and keeps the total refunded amount at 4000 paise.
- Test evidence: `test_refunds_cannot_exceed_due[4000-2000]`.

## 3. Ass