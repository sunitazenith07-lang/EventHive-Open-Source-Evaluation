# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
List the events in order, the expected state after each event, and the actual state your implementation returns.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `order = new_order("ORD-701", 45000)` | `status: "PLACED"`, `payment_status: "UNPAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: []` | `status: "PLACED"`, `payment_status: "UNPAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: []` |
| 2 | `{"event_id": "EV-01", "type": "payment_confirmed"}` | `status: "PLACED"`, `payment_status: "PAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ["EV-01"]` | `status: "PLACED"`, `payment_status: "PAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ["EV-01"]` |
| 3 | `{"event_id": "EV-02", "type": "restaurant_accepted"}` | `status: "ACCEPTED"`, `payment_status: "PAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ["EV-01", "EV-02"]` | `status: "ACCEPTED"`, `payment_status: "PAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ["EV-01", "EV-02"]` |
| 4 | `{"event_id": "EV-03", "type": "cancel_requested"}` | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due_paise: 45000`, `refunded_paise: 0`, `processed_event_ids: ["EV-01", "EV-02", "EV-03"]` | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due_paise: 45000`, `refunded_paise: 0`, `processed_event_ids: ["EV-01", "EV-02", "EV-03"]` |
| 5 | `{"event_id": "EV-04", "type": "refund_processed", "amount_paise": 20000}` | `status: "CANCELLED"`, `payment_status: "PAID"` (partial), `refund_due_paise: 45000`, `refunded_paise: 20000`, `processed_event_ids: ["EV-01", "EV-02", "EV-03", "EV-04"]` | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due_paise: 45000`, `refunded_paise: 20000`, `processed_event_ids: ["..."]` |
| 6 | `{"event_id": "EV-05", "type": "refund_processed", "amount_paise": 25000}` | `status: "CANCELLED"`, `payment_status: "REFUNDED"` (full), `refund_due_paise: 45000`, `refunded_paise: 45000`, `processed_event_ids: ["EV-01", "EV-02", "EV-03", "EV-04", "EV-05"]` | `status: "CANCELLED"`, `payment_status: "REFUNDED"`, `refund_due_paise: 45000`, `refunded_paise: 45000`, `processed_event_ids: ["..."]` |

## 2. Three edge cases
For each, state the input/event sequence, expected behaviour, actual observed result, and test that verifies it.

### Edge Case 1: Post-Dispatch Cancellation Attempt
- **Input/Sequence**: Order transitions `PLACED` $\rightarrow$ `restaurant_accepted` $\rightarrow$ `ACCEPTED` $\rightarrow$ `dispatch_started` $\rightarrow$ `OUT_FOR_DELIVERY`. Customer subsequently triggers `{"event_id": "EV-CANCEL", "type": "cancel_requested"}`.
- **Expected Behaviour**: The cancellation event must be safely ignored. Food has left the restaurant kitchen and is actively transported by the delivery partner. Order status must remain `OUT_FOR_DELIVERY`, and no refund liability may be created (`refund_due_paise` remains 0).
- **Actual Observed Result**: Order `status` remains `"OUT_FOR_DELIVERY"`, `refund_due_paise == 0`, and the order progresses to `DELIVERED` when `order_delivered` arrives.
- **Verifying Test**: `tests/test_contract.py:test_cancel_after_dispatch_is_ignored` and `tests/test_acceptance_matrix.py:test_order_state_transition_matrix`.

### Edge Case 2: Late Payment Confirmation on Unpaid Cancellation
- **Input/Sequence**: Order created as `PLACED` (`total_paise: 10000`, `payment_status: "UNPAID"`). Customer immediately cancels (`cancel_requested`), transitioning order to `CANCELLED`. Because payment was unpaid at time of cancellation, `refund_due_paise` initially remains 0. Subsequently, delayed payment webhook arrives: `{"event_id": "EV-PAY-LATE", "type": "payment_confirmed"}`.
- **Expected Behaviour**: The engine marks `payment_status = "PAID"`. Because the order is already in a terminal cancelled state where fulfillment cannot occur, the system must immediately recognize customer refund liability by setting `refund_due_paise = total_paise` (10000 paise). Subsequent refund events must then be eligible for processing.
- **Actual Observed Result**: Order updates `payment_status` to `"PAID"` and populates `refund_due_paise = 10000`. When a refund event of 10000 arrives, it successfully processes and transitions payment status to `"REFUNDED"`.
- **Verifying Test**: Implementation logic in `service.py:apply_order_event` (`kind == "payment_confirmed"` branch) satisfying scenario requirement from `STUDENT_PROBLEM_STATEMENT.md:6`.

### Edge Case 3: Over-Refund Bounds and Non-Integer/Boolean Data Types
- **Input/Sequence**: Order in status `CANCELLED`, `payment_status: "PAID"`, `refund_due_paise: 5000`. Two distinct invalid refund events arrive:
  1. `{"event_id": "R1", "type": "refund_processed", "amount_paise": True}` (Python `bool` subtype exploit).
  2. `{"event_id": "R2", "type": "refund_processed", "amount_paise": 6000}` (Exceeding outstanding due of 5000).
- **Expected Behaviour**: Both events must be rejected. The boolean amount must be rejected by checking `type(amount) is int`. The 6000 amount must be rejected by verifying `refunded_paise + amount <= refund_due_paise`. Total refunded amount must remain 0.
- **Actual Observed Result**: `refunded_paise` remains `0` after both events, and `payment_status` remains `"PAID"`.
- **Verifying Test**: `tests/test_acceptance_matrix.py:test_invalid_refund_amounts_are_ignored` and `tests/test_acceptance_matrix.py:test_refunds_cannot_exceed_due`.

## 3. Assumptions and limitations
Document assumptions about cancellation eligibility, dispatch transitions, refund due/refunded amounts, and any unresolved issue.
- **Cancellation Finality**: Cancellation is permitted only when status is `PLACED` or `ACCEPTED`. Once dispatch begins (`OUT_FOR_DELIVERY`), cancellation is strictly rejected to protect delivery partner operational effort and prevent food waste.
- **Refund Eligibility Triple Invariant**: Refunds are strictly tied to premature terminal failure (`REJECTED` or `CANCELLED`) for paid orders (`payment_status == "PAID"`) with outstanding liability (`refund_due_paise > 0`). Completed deliveries (`DELIVERED`) cannot be refunded via automated order-event webhooks.
- **Integer Paise Arithmetic**: All financial calculations are constrained to strictly positive integers (`paise >= 1`, $1\text{ INR} = 100\text{ paise}$). Floating-point values are rejected to prevent IEEE-754 currency drift.
- **Schema Key Duality**: The system assumes internal domain records identify price via `total_paise` (per `models.py`), while external payment providers identify settlement price via `amount_paise`. Reconciliation normalizes this via `_get_amount` fallback.
- **Unresolved Scope Boundaries**: Cross-border foreign currency conversions, tax deduction withholding allocations, and out-of-order timestamp re-sequencing are outside the evaluation scope.
