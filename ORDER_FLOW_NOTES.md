# ORDER_FLOW_NOTES.md

## 1. Example order-event sequence
Example order: `ORD-42`, total `5000` paise.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` | `payment_status == "PAID"`, status remains `PLACED` | `payment_status == "PAID"` |
| 2 | `restaurant_accepted` | status becomes `ACCEPTED` | status becomes `ACCEPTED` |
| 3 | `dispatch_started` | status becomes `OUT_FOR_DELIVERY` | status becomes `OUT_FOR_DELIVERY` |
| 4 | `order_delivered` | status becomes `DELIVERED` | status becomes `DELIVERED` |

This sequence is verified by the state-transition tests in `tests/test_acceptance_matrix.py` and the contract check in `tests/test_contract.py`.

## 2. Three edge cases
1. Duplicate event replay: input is `payment_confirmed` twice with the same `event_id`; expected result is that the second write is ignored and `processed_event_ids` remains `['E-1']`. Actual result: no mutation on reprocessing.
2. Cancel after dispatch: order in `OUT_FOR_DELIVERY` receives `cancel_requested`; expected result is no status change because dispatch is already underway. Actual result: status remains `OUT_FOR_DELIVERY`.
3. Refund overrun: order is `CANCELLED` and `payment_status == "PAID"`; a refund request of `1200` against a `1000` due amount should be ignored. Actual result: `refunded_paise == 0` and no crash.

## 3. Assumptions and limitations
- Cancellation is only valid while the order is still `PLACED` or `ACCEPTED`.
- A dispatch-started event is the gate to `OUT_FOR_DELIVERY`; a later cancellation request is ignored.
- Refunds only apply to eligible paid `REJECTED` or `CANCELLED` orders, and the service checks the outstanding amount before applying a partial refund.
- No unresolved functional issues remain in the repository test suite after the fix; the only explicit limitation is that malformed event payloads are treated as safe no-ops rather than raising errors.
