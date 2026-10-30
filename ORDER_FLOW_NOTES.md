# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` | Status: `PLACED`, Payment: `PAID` | Status: `PLACED`, Payment: `PAID` |
| 2 | `restaurant_accepted` | Status: `ACCEPTED`, Payment: `PAID` | Status: `ACCEPTED`, Payment: `PAID` |
| 3 | `cancel_requested` | Status: `CANCELLED`, Refund Due: `1000` | Status: `CANCELLED`, Refund Due: `1000` |
| 4 | `refund_processed` (1000 paise) | Status: `CANCELLED`, Payment: `REFUNDED` | Status: `CANCELLED`, Payment: `REFUNDED` |

## 2. Three edge cases
1. **Boolean Refund Input:** Passing `amount_paise=True`. Expected to be ignored. Actual result: Ignored successfully. Verified by `test_invalid_refund_amounts_are_ignored`.
2. **Post-Dispatch Cancellation:** Requesting cancellation after `dispatch_started`. Expected status to remain `OUT_FOR_DELIVERY`. Actual result: Status unchanged. Verified by `test_order_state_transition_matrix`.
3. **Event Replay (Idempotency):** Sending the same `payment_confirmed` event twice. Expected payment state to remain `PAID` and not duplicate processing. Actual result: Handled safely via `processed_event_ids`. Verified by `test_payment_event_replay_idempotent`.

## 3. Assumptions and limitations
- Assumptions: All monetary values are integers in paise. Orders cannot be cancelled once dispatched.
- Limitations: In-memory state dictionary storage only (no external database persistence).
