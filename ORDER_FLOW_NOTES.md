# ORDER_FLOW_NOTES.md — Required Submission

## 1. Example order-event sequence
Order initialized: `new_order("ORD-901", 25000)` (order for ₹250.00, `status="PLACED"`, `payment_status="UNPAID"`).

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `EVT-01`: `payment_confirmed` | `status: "PLACED"`, `payment_status: "PAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ["EVT-01"]` | `status: "PLACED"`, `payment_status: "PAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ["EVT-01"]` |
| 2 | `EVT-02`: `restaurant_accepted` | `status: "ACCEPTED"`, `payment_status: "PAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ["EVT-01", "EVT-02"]` | `status: "ACCEPTED"`, `payment_status: "PAID"`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ["EVT-01", "EVT-02"]` |
| 3 | `EVT-03`: `cancel_requested` | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due_paise: 25000`, `refunded_paise: 0`, `processed_event_ids: ["EVT-01", "EVT-02", "EVT-03"]` | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due_paise: 25000`, `refunded_paise: 0`, `processed_event_ids: ["EVT-01", "EVT-02", "EVT-03"]` |
| 4 | `EVT-04`: `refund_processed` (`amount_paise: 10000`) | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due_paise: 25000`, `refunded_paise: 10000`, `processed_event_ids: ["EVT-01", "EVT-02", "EVT-03", "EVT-04"]` | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due_paise: 25000`, `refunded_paise: 10000`, `processed_event_ids: ["EVT-01", "EVT-02", "EVT-03", "EVT-04"]` |
| 5 | `EVT-05`: `refund_processed` (`amount_paise: 15000`) | `status: "CANCELLED"`, `payment_status: "REFUNDED"`, `refund_due_paise: 25000`, `refunded_paise: 25000`, `processed_event_ids: ["EVT-01", "EVT-02", "EVT-03", "EVT-04", "EVT-05"]` | `status: "CANCELLED"`, `payment_status: "REFUNDED"`, `refund_due_paise: 25000`, `refunded_paise: 25000`, `processed_event_ids: ["EVT-01", "EVT-02", "EVT-03", "EVT-04", "EVT-05"]` |
| 6 | `EVT-05`: `refund_processed` (`amount_paise: 15000`) (duplicate replay) | No state mutation; `refunded_paise: 25000`, `payment_status: "REFUNDED"`, `processed_event_ids` unchanged | `refunded_paise: 25000`, `payment_status: "REFUNDED"`, `processed_event_ids: ["EVT-01", "EVT-02", "EVT-03", "EVT-04", "EVT-05"]` |

## 2. Three edge cases
1. **Cancellation Attempted After Dispatch**:
   - *Input/Event sequence*: Order transitions `PLACED` -> `ACCEPTED` -> `dispatch_started` (status becomes `OUT_FOR_DELIVERY`). Customer then issues `cancel_requested`.
   - *Expected behaviour*: Cancellation is rejected because the order is already in transit. Status remains `OUT_FOR_DELIVERY`, and no refund is marked due.
   - *Actual result*: Status stays `OUT_FOR_DELIVERY`, `refund_due_paise: 0`.
   - *Verification test*: `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` and `tests/test_regression.py::test_cancellation_after_dispatch_and_delivery_is_strictly_ignored`.

2. **Refund Exceeding Outstanding Refundable Balance**:
   - *Input/Event sequence*: Cancelled order with ₹50.00 (`5000` paise) due receives a partial refund of ₹30.00 (`3000` paise). Outstanding balance is now ₹20.00 (`2000` paise). A second refund event requests ₹25.00 (`2500` paise).
   - *Expected behaviour*: Because 2500 exceeds the remaining due amount of 2000, the second refund event is rejected. Total refunded remains 3000.
   - *Actual result*: `refunded_paise` remains 3000, `payment_status` remains `PAID`.
   - *Verification test*: `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due` and `tests/test_regression.py::test_cumulative_partial_refunds_transition_to_refunded_on_exact_completion`.

3. **Late-Arriving Payment Confirmation After Restaurant Rejection**:
   - *Input/Event sequence*: Order is created `PLACED` and `UNPAID`. Restaurant sends `restaurant_rejected` (status becomes `REJECTED`, `refund_due_paise` is 0 because payment was not confirmed yet). Gateway subsequently delivers late `payment_confirmed`.
   - *Expected behaviour*: Service recognizes order is already terminated and sets `payment_status="PAID"` and updates `refund_due_paise` to the full order amount (`total_paise`), making the customer eligible for automated refunding.
   - *Actual result*: `payment_status == "PAID"`, `refund_due_paise == total_paise`.
   - *Verification test*: `tests/test_regression.py::test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due`.

## 3. Assumptions and limitations
- **Cancellation Eligibility**: Customers may only cancel when the order is in `PLACED` or `ACCEPTED` status. Once dispatched (`OUT_FOR_DELIVERY`) or delivered (`DELIVERED`), cancellations are rejected.
- **Refund Eligibility**: Refunds require both that the order was paid (`payment_status == "PAID"`) and that the order was terminated (`REJECTED` or `CANCELLED`).
- **Partial vs Completed Refunds**: `refund_due_paise` tracks the total obligation, while `refunded_paise` tracks the processed sum. Status remains `PAID` until `refunded_paise >= refund_due_paise`, upon which it transitions to `REFUNDED`.
- **Idempotency**: Every processed event ID is recorded. Any re-submitted event with an already processed `event_id` is ignored as an idempotent no-op.
