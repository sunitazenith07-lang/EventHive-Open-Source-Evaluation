# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
Order initialized: `new_order("ORD-500", 6000)` (`status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`).

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `{"event_id": "e1", "type": "payment_confirmed"}` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0` | `{"status": "PLACED", "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0, "processed_event_ids": ["e1"]}` |
| 2 | `{"event_id": "e2", "type": "restaurant_accepted"}` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0` | `{"status": "ACCEPTED", "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0, "processed_event_ids": ["e1", "e2"]}` |
| 3 | `{"event_id": "e3", "type": "cancel_requested"}` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=6000`, `refunded_paise=0` | `{"status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 6000, "refunded_paise": 0, "processed_event_ids": ["e1", "e2", "e3"]}` |
| 4 | `{"event_id": "e4", "type": "refund_processed", "amount_paise": 3000}` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=6000`, `refunded_paise=3000` | `{"status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 6000, "refunded_paise": 3000, "processed_event_ids": ["e1", "e2", "e3", "e4"]}` |
| 5 | `{"event_id": "e5", "type": "refund_processed", "amount_paise": 3000}` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=6000`, `refunded_paise=6000` | `{"status": "CANCELLED", "payment_status": "REFUNDED", "refund_due_paise": 6000, "refunded_paise": 6000, "processed_event_ids": ["e1", "e2", "e3", "e4", "e5"]}` |

## 2. Three edge cases
For each, state the input/event sequence, expected behaviour, actual observed result, and test that verifies it.

1. **Cancellation attempted after dispatch (`OUT_FOR_DELIVERY`):**
   - *Sequence:* Order transitions `PLACED -> ACCEPTED -> OUT_FOR_DELIVERY` (`payment_status="PAID"`). Then `cancel_requested` event arrives.
   - *Expected behaviour:* Cancellation is ignored. Order status remains `OUT_FOR_DELIVERY`. No refund due is scheduled (`refund_due_paise=0`).
   - *Actual observed result:* Status remained `OUT_FOR_DELIVERY` and `refund_due_paise=0`.
   - *Test verification:* `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` and `tests/test_regression.py::test_cancellation_after_dispatch_does_not_affect_state`.

2. **Payment confirmed after rejection or cancellation:**
   - *Sequence:* Order created as `UNPAID`, then `restaurant_rejected` arrives (`status="REJECTED"`, `refund_due_paise=0`). Subsequently, a delayed `payment_confirmed` arrives.
   - *Expected behaviour:* Order payment status updates to `PAID` and `refund_due_paise` is set to the full order `total_paise` so the customer receives their money back.
   - *Actual observed result:* `payment_status="PAID"`, `refund_due_paise=4500`.
   - *Test verification:* `tests/test_regression.py::test_payment_confirmed_after_rejection_sets_refund_due`.

3. **Cumulative refund overflow rejection:**
   - *Sequence:* Paid cancelled order of 5000 paise with 3000 paise already refunded. Incoming refund event requests 2500 paise.
   - *Expected behaviour:* Remaining refundable due is $5000 - 3000 = 2000$. Since 2500 exceeds 2000, the refund is disallowed and ignored completely (not partially clamped). Total refunded remains 3000 paise.
   - *Actual observed result:* `refunded_paise=3000`, `payment_status="PAID"`.
   - *Test verification:* `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due` and `tests/test_regression.py::test_refund_rejected_when_exceeding_remaining_due_after_partial`.

## 3. Assumptions and limitations
- **Integer Paise Representation:** All monetary values (`total_paise`, `refund_due_paise`, `refunded_paise`, `amount_paise`) are strictly positive integers. Floating-point numbers, negative values, and non-numeric types are invalid.
- **Cancellation Cutoff:** Orders can be cancelled by customer request only while in `PLACED` or `ACCEPTED` states. Once dispatch has started (`OUT_FOR_DELIVERY`), cancellation cannot be initiated via normal order events.
- **Refund Eligibility:** Refunds are permitted only when an order is in terminal cancelled/rejected status (`REJECTED` or `CANCELLED`), has been paid (`payment_status="PAID"`), and has non-zero remaining refundable due. Orders in transit or delivered cannot process automated cancellation refunds via this handler.
- **Key Normalization in Reconciliation:** Internal records primarily key order amounts by `total_paise`, while external providers use `amount_paise`. Reconciliation accepts either key transparently.
