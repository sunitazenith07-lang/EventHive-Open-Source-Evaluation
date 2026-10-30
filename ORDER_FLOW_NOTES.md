# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
List the events in order, the expected state after each event, and the actual state your implementation returns.

Order initialized: `order_id="ORD-FLOW-01"`, `total_paise=5000`, `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` (`event_id="EV-1"`) | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1"]` |
| 2 | `restaurant_accepted` (`event_id="EV-2"`) | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2"]` |
| 3 | `cancel_requested` (`event_id="EV-3"`) | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=5000`, `refunded_paise=0` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=5000`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2", "EV-3"]` |
| 4 | `refund_processed` (`event_id="EV-4"`, `amount_paise=2000`) | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=5000`, `refunded_paise=2000` (Partial) | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=5000`, `refunded_paise=2000`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4"]` |
| 5 | `refund_processed` (`event_id="EV-5"`, `amount_paise=3000`) | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=5000`, `refunded_paise=5000` (Full) | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=5000`, `refunded_paise=5000`, `processed_event_ids=[..., "EV-5"]` |

## 2. Three edge cases
For each, state the input/event sequence, expected behaviour, actual observed result, and test that verifies it.
1. **Cancellation After Dispatch**:
   - Sequence: Order in `OUT_FOR_DELIVERY` receives `cancel_requested`.
   - Expected: Order cannot be cancelled once dispatched; remains `OUT_FOR_DELIVERY`.
   - Actual: Status preserved as `OUT_FOR_DELIVERY`.
   - Test: `test_cancel_after_dispatch_is_ignored` and `test_order_state_transition_matrix`.
2. **Excessive Refund Attempt**:
   - Sequence: Cancelled paid order with `refund_due_paise=5000` receives `refund_processed` with `amount_paise=6000`.
   - Expected: Exceeds outstanding due; amount rejected without modifying `refunded_paise`.
   - Actual: `refunded_paise` remains `0`, `payment_status` remains `PAID`.
   - Test: `test_refund_cannot_exceed_amount_due` and `test_invalid_refund_amounts_are_ignored`.
3. **Replay of Confirmed Payment Event**:
   - Sequence: Order receives `payment_confirmed` with `event_id="EV-001"`, then re-receives the exact same event.
   - Expected: Idempotent execution; second event ignored without state mutation or duplicate IDs.
   - Actual: `processed_event_ids` contains `["EV-001"]` once; state intact.
   - Test: `test_payment_event_replay_idempotent` and `test_duplicate_event_is_idempotent`.

## 3. Assumptions and limitations
- Orders can only transition to `CANCELLED` if requested before dispatch (while `PLACED` or `ACCEPTED`).
- All currency values are non-negative integer paise.
- Partial refunds keep `payment_status="PAID"`; only reaching full `refund_due_paise` transitions status to `"REFUNDED"`.
