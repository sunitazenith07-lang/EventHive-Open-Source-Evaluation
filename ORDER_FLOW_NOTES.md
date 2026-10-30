# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
Step-by-step trace of order `ORD-777` with total amount 25000 paise (₹250.00):

| Step | Event | Details | Expected order state | Actual result |
|---|---|---|---|---|
| Initial | Order created | `new_order("ORD-777", 25000)` | `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]` | `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]` |
| 1 | `payment_confirmed` | `event_id="EV-1"` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1"]` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=['EV-1']` |
| 2 | `restaurant_accepted` | `event_id="EV-2"` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2"]` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=['EV-1', 'EV-2']` |
| 3 | `cancel_requested` | `event_id="EV-3"` (cancelled before dispatch) | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=25000`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2", "EV-3"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=25000`, `refunded_paise=0`, `processed_event_ids=['EV-1', 'EV-2', 'EV-3']` |
| 4 | `refund_processed` | `event_id="EV-4"`, `amount_paise=10000` (partial refund) | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=25000`, `refunded_paise=10000`, `processed_event_ids=[..., "EV-4"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=25000`, `refunded_paise=10000`, `processed_event_ids=['EV-1', 'EV-2', 'EV-3', 'EV-4']` |
| 5 | `refund_processed` | `event_id="EV-5"`, `amount_paise=15000` (remaining balance) | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=25000`, `refunded_paise=25000`, `processed_event_ids=[..., "EV-5"]` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=25000`, `refunded_paise=25000`, `processed_event_ids=['EV-1', 'EV-2', 'EV-3', 'EV-4', 'EV-5']` |
| 6 | `refund_processed` | `event_id="EV-6"`, `amount_paise=5000` (extra refund attempt) | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refunded_paise=25000` (ignored, cannot exceed due) | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=25000`, `refunded_paise=25000` |

---

## 2. Three edge cases

### Edge Case 1: Cancellation after dispatch is ignored
- **Input sequence:**
  1. `order = new_order("ORD-LATE", 45000, "ACCEPTED")`
  2. `dispatch_started` event arrives -> Status changes to `OUT_FOR_DELIVERY`.
  3. `cancel_requested` event arrives.
- **Expected behaviour:** Order must remain `OUT_FOR_DELIVERY`. The cancellation should be ignored because the food is already on its way, and `refund_due_paise` should remain 0.
- **Actual result:** `order["status"] == "OUT_FOR_DELIVERY"`, `order["refund_due_paise"] == 0`.
- **Test verifying it:** `tests/test_regression_and_edge_cases.py::test_cancel_after_dispatch_ignored`.

### Edge Case 2: Duplicate event replayed with a different payload
- **Input sequence:**
  1. `order = new_order("ORD-DUP", 20000, "PLACED")`
  2. `payment_confirmed` with `event_id="EV-1"` arrives -> `payment_status` becomes `PAID`.
  3. A duplicate event arrives with the same `event_id="EV-1"`, but with `type="restaurant_rejected"`.
- **Expected behaviour:** Because `EV-1` is already in `processed_event_ids`, the event is recognized as a duplicate and ignored. The order must stay `PLACED` and not change to `REJECTED`.
- **Actual result:** `order["status"] == "PLACED"`, `order["processed_event_ids"] == ["EV-1"]`.
- **Test verifying it:** `tests/test_regression_and_edge_cases.py::test_duplicate_event_with_same_id_is_ignored`.

### Edge Case 3: Late payment on a cancelled or rejected order
- **Input sequence:**
  1. `order = new_order("ORD-LATE", 15000, "PLACED")` (unpaid).
  2. `cancel_requested` arrives before payment -> `status="CANCELLED"`, `payment_status="UNPAID"`, `refund_due_paise=0`.
  3. A delayed `payment_confirmed` webhook arrives from the gateway.
- **Expected behaviour:** The order was cancelled before payment arrived, but the customer was still charged. When `payment_confirmed` arrives, `payment_status` becomes `PAID`, and `refund_due_paise` must be set to `total_paise` (15000) so that a refund can be issued.
- **Actual result:** `order["status"] == "CANCELLED"`, `order["payment_status"] == "PAID"`, `order["refund_due_paise"] == 15000`.
- **Test verifying it:** `tests/test_regression_and_edge_cases.py::test_late_payment_after_cancellation`.

---

## 3. Assumptions and limitations
- **Cancellation:** Customers can only cancel while the order is in `PLACED` or `ACCEPTED`. Once dispatch begins (`OUT_FOR_DELIVERY`), cancellation is blocked.
- **Order Flow:** Orders must be `ACCEPTED` by the restaurant before they can transition to `OUT_FOR_DELIVERY`. They cannot jump directly from `PLACED` to `OUT_FOR_DELIVERY`.
- **Refund Rules:**
  - Amounts are in integer paise (positive values only).
  - Only `CANCELLED` or `REJECTED` orders that have been paid (`payment_status == "PAID"`) can be refunded.
  - Partial refunds keep `payment_status` as `PAID`. It is updated to `REFUNDED` only when `refunded_paise >= refund_due_paise`.
  - Refunds cannot exceed the remaining due amount (`refund_due_paise - refunded_paise`).
- **Limitations:**
  - The implementation operates entirely in-memory and handles events sequentially. In a multi-server setup, distributed locking (e.g. Redis) or database row locks would be needed to handle concurrent webhooks safely.
