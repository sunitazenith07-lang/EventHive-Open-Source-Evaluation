# ORDER_FLOW_NOTES.md — OrderOps

## Example: paid order rejected, then refunded
This is an illustrative sequence consistent with the corrected service. The sequence below is **not** a separately recorded demo trace.

Initial order: `new_order("O-EXAMPLE", 5000)`; status `PLACED`, payment `UNPAID`, refund due 0, refunded 0.

| Step | Event | Expected status / payment / due / refunded |
|---|---|---|
| 1 | `payment_confirmed` (P1) | PLACED / PAID / 0 / 0 |
| 2 | `restaurant_rejected` (R1) | REJECTED / PAID / 5000 / 0 |
| 3 | `refund_processed` (F1, amount 2000) | REJECTED / PAID / 5000 / 2000 |
| 4 | `refund_processed` (F2, amount 3000) | REJECTED / REFUNDED / 5000 / 5000 |

Expected behavior is supported by the visible refund and transition tests. Verify the precise sequence separately before recording it as individually observed.

## Three edge cases
1. **Duplicate notification:** Replay F1 with the same event ID. Expected: refunded amount remains 2000 after the replay. Covered by the idempotency behavior.
2. **Excess refund:** Attempt 4000 then 2000 against 5000 due. Expected: second refund rejected, leaving 4000 refunded. Covered by `test_refunds_cannot_exceed_due`.
3. **Cancel after dispatch:** Starting at OUT_FOR_DELIVERY, apply `cancel_requested`. Expected: remains OUT_FOR_DELIVERY. Covered by `test_cancel_after_dispatch_is_ignored`.

## Assumptions
- Currency is stored as integer paise; booleans are invalid amounts.
- Normal refund processing requires status CANCELLED or REJECTED, payment status PAID, and a positive refund due.
- The order retains cumulative refunded amount separately from refund due.
- An event ID already processed cannot mutate order state again.
- Cancellation after dispatch does not transition an order to CANCELLED.

## Limitations
- The example uses synthetic data and does not interact with payment providers.
- Out-of-order payment/refund events and malformed stored order records may require additional requirements and tests.
