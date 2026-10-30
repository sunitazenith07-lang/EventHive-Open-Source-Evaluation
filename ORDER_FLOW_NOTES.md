# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
Order initialized: `new_order("ORD-8801", 5000)`
Initial state: `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]`.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `{"event_id": "EV-01", "type": "payment_confirmed"}` | `status="PLACED"`, `payment_status="PAID"`, `refund_due=0`, `refunded=0`, `events=["EV-01"]` | `status="PLACED"`, `payment_status="PAID"`, `refund_due=0`, `refunded=0`, `events=["EV-01"]` |
| 2 | `{"event_id": "EV-02", "type": "restaurant_accepted"}` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due=0`, `refunded=0`, `events=["EV-01", "EV-02"]` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due=0`, `refunded=0`, `events=["EV-01", "EV-02"]` |
| 3 | `{"event_id": "EV-03", "type": "cancel_requested"}` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due=5000`, `refunded=0`, `events=["EV-01", "EV-02", "EV-03"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due=5000`, `refunded=0`, `events=["EV-01", "EV-02", "EV-03"]` |
| 4 | `{"event_id": "EV-04", "type": "refund_processed", "amount_paise": 2000}` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due=5000`, `refunded=2000`, `events=["EV-01", "EV-02", "EV-03", "EV-04"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due=5000`, `refunded=2000`, `events=["EV-01", "EV-02", "EV-03", "EV-04"]` |
| 5 | `{"event_id": "EV-05", "type": "refund_processed", "amount_paise": 3000}` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due=5000`, `refunded=5000`, `events=["EV-01", "EV-02", "EV-03", "EV-04", "EV-05"]` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due=5000`, `refunded=5000`, `events=["EV-01", "EV-02", "EV-03", "EV-04", "EV-05"]` |

## 2. Three edge cases

### 1. Cancellation request after dispatch has started
- **Input sequence:**
  - Order initialized: `new_order("ORD-EDGE-1", 4500)`.
  - Event 1: `{"event_id": "E1", "type": "restaurant_accepted"}` -> `status="ACCEPTED"`.
  - Event 2: `{"event_id": "E2", "type": "dispatch_started"}` -> `status="OUT_FOR_DELIVERY"`.
  - Event 3: `{"event_id": "E3", "type": "cancel_requested"}`.
- **Expected behaviour:** Cancellation is prohibited once the delivery partner has departed (`OUT_FOR_DELIVERY`). Status must remain `OUT_FOR_DELIVERY`, and no refund due is assigned.
- **Actual observed result:** `status == "OUT_FOR_DELIVERY"`, `refund_due_paise == 0`.
- **Verifying test:** `tests/test_regression.py::test_cancellation_after_dispatch_is_ignored`.

### 2. Duplicate refund event idempotency
- **Input sequence:**
  - Order is in `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=2000`.
  - Event 1: `{"event_id": "REF-10", "type": "refund_processed", "amount_paise": 1000}`.
  - Event 2: `{"event_id": "REF-10", "type": "refund_processed", "amount_paise": 1000}` (replay).
- **Expected behaviour:** Idempotency guard matches `event_id="REF-10"`. Replayed event is ignored; refund is counted exactly once (1000 paise), and `payment_status` stays `PAID`.
- **Actual observed result:** `refunded_paise == 1000`, `payment_status == "PAID"`, `processed_event_ids == ["REF-10"]`.
- **Verifying test:** `tests/test_regression.py::test_duplicate_event_idempotency_does_not_double_count`.

### 3. Out-of-order payment confirmation following restaurant rejection
- **Input sequence:**
  - Order initialized: `new_order("ORD-EDGE-3", 1500)`.
  - Event 1: `{"event_id": "E1", "type": "restaurant_rejected"}` -> `status="REJECTED"`, `payment_status="UNPAID"`, `refund_due_paise=0`.
  - Event 2: `{"event_id": "E2", "type": "payment_confirmed"}` (delayed arrival from payment gateway).
- **Expected behaviour:** The order was already rejected, but customer payment has now cleared. The system updates `payment_status="PAID"` and immediately flags `refund_due_paise=1500` so customer funds are returned.
- **Actual observed result:** `status == "REJECTED"`, `payment_status == "PAID"`, `refund_due_paise == 1500`.
- **Verifying test:** `tests/test_regression.py::test_late_payment_after_rejection_activates_refund_due`.

## 3. Assumptions and limitations
- **Cancellation eligibility:** An order may only be cancelled while in `PLACED` or `ACCEPTED` status. Once dispatched (`OUT_FOR_DELIVERY`) or delivered (`DELIVERED`), cancellations are rejected.
- **Dispatch transitions:** Dispatch can only be initiated from `ACCEPTED` status. Dispatches on `PLACED`, `REJECTED`, or `CANCELLED` orders are ignored.
- **Refund due & payment status:** Refunds are only due if payment was confirmed (`PAID`). Partial refunds leave the order in `PAID` status; only when `refunded_paise == refund_due_paise` does the payment status transition to `REFUNDED`.
- **Currency & precision:** All amounts are strictly positive non-boolean integers representing paise ($1 \text{ INR} = 100 \text{ paise}$). Fractional or boolean amounts are rejected.
- **Concurrency & distributed limitations:** The service functions operate synchronously in-memory. For distributed architectures, external concurrency controls (such as distributed locks or PostgreSQL row-level locks) are necessary to sequence concurrent event deliveries.
