# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
- List the events in order, the expected state after each event, and the actual state your implementation returns.
Order initialized: `new_order("ORD-8801", 6500)` -> Status: `PLACED`, Payment: `UNPAID`, Refund Due: `0`, Refunded: `0`.
| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 1 | `payment_confirmed` (`event_id="EV-1"`) | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1"]` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1"]` |
| 2 | `restaurant_accepted` (`event_id="EV-2"`) | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2"]` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2"]` |
| 3 | `cancel_requested` (`event_id="EV-3"`) | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=6500`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2", "EV-3"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=6500`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2", "EV-3"]` |
| 4 | `refund_processed` (`event_id="EV-4"`, `amount_paise=3000`) | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=6500`, `refunded_paise=3000` (partial refund remains PAID) | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=6500`, `refunded_paise=3000` |
| 5 | `refund_processed` (`event_id="EV-5"`, `amount_paise=3500`) | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=6500`, `refunded_paise=6500` (full refund reached) | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=6500`, `refunded_paise=6500` |
| 6 | `refund_processed` (`event_id="EV-5"` duplicate replay) | No-op due to event idempotency; state remains unchanged | State unchanged; `processed_event_ids` retains `["EV-1", "EV-2", "EV-3", "EV-4", "EV-5"]` |

## 2. Three edge cases
- For each, state the input/event sequence, expected behaviour, actual observed result, and test that verifies it.
- 1.
- 2.
- 3.
1. **Cancellation After Dispatch**:
   - *Input/Event Sequence*: Order transitions `PLACED` -> `ACCEPTED` -> `dispatch_started` (`OUT_FOR_DELIVERY`), then receives `cancel_requested`.
   - *Expected Behaviour*: The cancellation request is ignored; order status remains `OUT_FOR_DELIVERY` and `refund_due_paise` remains 0.
   - *Actual Observed Result*: Status remains `OUT_FOR_DELIVERY`; order proceeds to delivery without cancellation.
   - *Test Evidence*: `tests/test_contract.py::test_cancel_after_dispatch_is_ignored`.
2. **Late Payment Confirmation Arriving After Rejection or Cancellation**:
   - *Input/Event Sequence*: Order is `PLACED`, restaurant issues `restaurant_rejected` (or customer cancels) while order is still `UNPAID`. Subsequently, `payment_confirmed` webhook arrives.
   - *Expected Behaviour*: Payment status transitions to `PAID`, and `refund_due_paise` is immediately set to `total_paise` so the customer can be refunded.
   - *Actual Observed Result*: Order correctly records `payment_status="PAID"` and `refund_due_paise=total_paise`.
   - *Test Evidence*: `tests/test_regression.py::test_late_payment_on_previously_cancelled_order`.
3. **Cumulative Over-Refund Protection**:
   - *Input/Event Sequence*: A cancelled paid order with 5000 paise due receives a partial refund of 4000 paise (`refunded_paise=4000`, `outstanding=1000`), followed by another refund event of 2000 paise.
   - *Expected Behaviour*: Second refund exceeds the outstanding 1000 paise refundable amount; it is completely rejected without modifying `refunded_paise`.
   - *Actual Observed Result*: Second refund is rejected; `refunded_paise` remains 4000 paise.
   - *Test Evidence*: `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due[4000-2000]`.

## 3. Assumptions and limitations
- Document assumptions about cancellation eligibility, dispatch transitions, refund due/refunded amounts, and any unresolved issue.
- **Cancellation Eligibility**: Cancellation is permitted strictly when order status is `PLACED` or `ACCEPTED`. Once dispatch begins (`OUT_FOR_DELIVERY` or `DELIVERED`), cancellations are rejected.
- **Refund Eligibility**: Refunds apply exclusively to `CANCELLED` or `REJECTED` orders where `payment_status == "PAID"`. Orders in `PLACED`, `ACCEPTED`, or `DELIVERED` status are not eligible for direct processing via standard `refund_processed` events without prior cancellation/rejection.
- **Idempotency Scope**: An event is identified by its `event_id`. Replays of an identical `event_id` are ignored.
- **Paise Currency Units**: All currency amounts represent integer paise (1 INR = 100 paise). Non-integer values (floats, strings, booleans) are rejected.