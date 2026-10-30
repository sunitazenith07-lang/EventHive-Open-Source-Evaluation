# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
Below is a realistic end-to-end lifecycle for an order (`ORD-999`) initialized with `total_paise = 4500` that undergoes payment, cancellation, and two-stage refund processing:

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| Initial | `new_order("ORD-999", 4500)` | `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]` | `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]` |
| 1 | `ev("EV-1", "payment_confirmed")` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1"]` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1"]` |
| 2 | `ev("EV-2", "restaurant_accepted")` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2"]` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2"]` |
| 3 | `ev("EV-3", "cancel_requested")` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=4500`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2", "EV-3"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=4500`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2", "EV-3"]` |
| 4 | `ev("EV-4", "refund_processed", amount_paise=2000)` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=4500`, `refunded_paise=2000`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=4500`, `refunded_paise=2000`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4"]` |
| 5 | `ev("EV-5", "refund_processed", amount_paise=2500)` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=4500`, `refunded_paise=4500`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4", "EV-5"]` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=4500`, `refunded_paise=4500`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4", "EV-5"]` |

## 2. Three edge cases

### Edge Case 1: Cancellation attempted after delivery partner dispatch
- **Input / Event sequence:**
  1. `order = new_order("ORD-E1", 3000, "ACCEPTED")` with `payment_status="PAID"`
  2. `dispatch_started` -> order transitions to `"OUT_FOR_DELIVERY"`
  3. Customer attempts `cancel_requested`
- **Expected behaviour:**
  Cancellation must be ignored. Status remains `"OUT_FOR_DELIVERY"`, and no refund due is recorded (`refund_due_paise == 0`).
- **Actual observed result:**
  Order status remains `"OUT_FOR_DELIVERY"` with `refund_due_paise == 0`.
- **Test verifying it:**
  `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` and `tests/test_regression.py::test_cannot_cancel_out_for_delivery_or_delivered`.

### Edge Case 2: Out-of-order payment confirmation following restaurant rejection
- **Input / Event sequence:**
  1. `order = new_order("ORD-E2", 5000, "PLACED")` with `payment_status="UNPAID"`
  2. `restaurant_rejected` -> order transitions to `"REJECTED"`, `refund_due_paise == 0` (unpaid)
  3. `payment_confirmed` arrives late
- **Expected behaviour:**
  Order remains `"REJECTED"`, `payment_status` updates to `"PAID"`, and `refund_due_paise` is initialized to full order value (`5000`). Subsequent valid `refund_processed` events are accepted.
- **Actual observed result:**
  `status="REJECTED"`, `payment_status="PAID"`, `refund_due_paise=5000`, and full refund succeeds.
- **Test verifying it:**
  `tests/test_regression.py::test_payment_confirmed_after_rejection_populates_refund_due`.

### Edge Case 3: Replay of duplicate refund event with identical event ID
- **Input / Event sequence:**
  1. `order = new_order("ORD-E3", 2000, "CANCELLED")` with `payment_status="PAID"`, `refund_due_paise=2000`
  2. `refund_processed` with `event_id="R-101"`, `amount_paise=1000`
  3. Duplicate `refund_processed` arrives with `event_id="R-101"`, `amount_paise=1000`
- **Expected behaviour:**
  The second refund event must be rejected by idempotency. `refunded_paise` remains `1000`, payment status remains `"PAID"` (not `"REFUNDED"`), and `"R-101"` appears only once in `processed_event_ids`.
- **Actual observed result:**
  `refunded_paise == 1000`, `payment_status == "PAID"`, `processed_event_ids == ["R-101"]`.
- **Test verifying it:**
  `tests/test_regression.py::test_duplicate_event_with_conflicting_payload_is_ignored`.

## 3. Assumptions and limitations
1. **Cancellation Eligibility:** Cancellations are only permitted when the order is in `PLACED` or `ACCEPTED` status. Once `dispatch_started` transitions the status to `OUT_FOR_DELIVERY`, cancellations are rejected.
2. **Refund Eligibility:** Refunds are only granted if the order is in a terminal failure state (`REJECTED` or `CANCELLED`) with `payment_status == "PAID"`. Live or in-transit orders cannot process refunds through this pipeline.
3. **Integer Currency:** All currency calculations strictly use integer paise. Non-integer amounts, negative values, and boolean flags are discarded.
4. **Deduplication Scope:** Idempotency is tracked per order dictionary using in-memory `processed_event_ids`. In a distributed environment, a shared transactional datastore with unique constraints on `(order_id, event_id)` would be necessary.
