# Order flow notes

## Example event sequence
Order: `ORD-42` with `total_paise = 5000`

| Step | Event | Expected state | Actual state |
|---|---|---|---|
| 1 | `payment_confirmed` | `payment_status` becomes `PAID`; status remains `PLACED` | `payment_status == "PAID"` |
| 2 | `restaurant_accepted` | order moves from `PLACED` to `ACCEPTED` | status becomes `ACCEPTED` |
| 3 | `dispatch_started` | order moves from `ACCEPTED` to `OUT_FOR_DELIVERY` | status becomes `OUT_FOR_DELIVERY` |
| 4 | `order_delivered` | order reaches `DELIVERED` | status becomes `DELIVERED` |

This sequence reflects the valid state machine implemented in `service.py` and verified by the acceptance tests in `tests/test_acceptance_matrix.py`.

## Refund calculation rule
A refund is only valid when:
- the order was paid,
- the order status is `CANCELLED` or `REJECTED`, and
- the refund request does not exceed the outstanding refundable amount.

The logic stores the total refund obligation in `refund_due_paise`, tracks the money already returned in `refunded_paise`, and updates `payment_status` to `REFUNDED` only when the full due amount has been processed.

## Three tested edge cases
1. Duplicate event replay: the same `event_id` is processed twice; the second application is ignored and the order remains unchanged.
2. Cancellation after dispatch: a `cancel_requested` event after `dispatch_started` does not change `OUT_FOR_DELIVERY` to `CANCELLED`.
3. Refund overrun: a refund request above the outstanding amount is rejected and does not increase `refunded_paise` past the valid threshold.

## Known limitations
- Invalid or unknown event payloads are rejected as safe no-ops rather than raising exceptions.
- The service deliberately avoids mutating state when the incoming payload is malformed or duplicate.
- No unresolved functional issues remain in the repository test suite at the current revision.
