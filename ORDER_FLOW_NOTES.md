# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
Below is the sequence exercised by `test_paid_rejection_partial_then_full_refund_flow`. Initial state: `order_id="O1"`, `total_paise=1000`, `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]`.

| Step | Event Applied | Expected order / payment / refund state | Actual result |
|---|---|---|---|
| 1 | `{"event_id": "e1", "type": "payment_confirmed"}` | `status: PLACED`<br>`payment_status: PAID`<br>`refund_due_paise: 0`<br>`refunded_paise: 0` | `status: PLACED`, `payment_status: PAID`, `refund_due_paise: 0`, `refunded_paise: 0`, `processed_event_ids: ['e1']` |
| 2 | `{"event_id": "e2", "type": "restaurant_rejected"}` | `status: REJECTED`<br>`payment_status: PAID`<br>`refund_due_paise: 1000`<br>`refunded_paise: 0` | `status: REJECTED`, `payment_status: PAID`, `refund_due_paise: 1000`, `refunded_paise: 0`, `processed_event_ids: ['e1', 'e2']` |
| 3 | `{"event_id": "r1", "type": "refund_processed", "amount_paise": 400}` | `status: REJECTED`<br>`payment_status: PAID` (partial)<br>`refund_due_paise: 1000`<br>`refunded_paise: 400` | `status: REJECTED`, `payment_status: PAID`, `refund_due_paise: 1000`, `refunded_paise: 400`, `processed_event_ids: ['e1', 'e2', 'r1']` |
| 4 | `{"event_id": "r2", "type": "refund_processed", "amount_paise": 600}` | `status: REJECTED`<br>`payment_status: REFUNDED` (complete)<br>`refund_due_paise: 1000`<br>`refunded_paise: 1000` | `status: REJECTED`, `payment_status: REFUNDED`, `refund_due_paise: 1000`, `refunded_paise: 1000`, `processed_event_ids: ['e1', 'e2', 'r1', 'r2']` |

## 2. Three edge cases

### Edge Case 1: Cancellation Attempted After Dispatch
- **Input sequence**:
  1. `order = new_order("ORD-1", 3000)`
  2. `apply_order_event(order, {"event_id": "e1", "type": "payment_confirmed"})`
  3. `apply_order_event(order, {"event_id": "e2", "type": "restaurant_accepted"})`
  4. `apply_order_event(order, {"event_id": "e3", "type": "dispatch_started"})`
  5. `apply_order_event(order, {"event_id": "e4", "type": "cancel_requested"})`
- **Expected behaviour**:
  The cancellation request must be ignored because delivery is already in progress. The order status must remain `OUT_FOR_DELIVERY`, and no refund due amount should be assigned.
- **Actual observed result**:
  `status` remained `OUT_FOR_DELIVERY`, `payment_status` remained `PAID`, `refund_due_paise` remained `0`.
- **Test verifying it**:
  `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` and `tests/test_acceptance_matrix.py::test_order_state_transition_matrix`.

### Edge Case 2: Duplicate / Replayed Partial Refund Event
- **Input sequence**:
  1. Order is `CANCELLED`, `payment_status="PAID"`, `refund_due_paise=4000`, `refunded_paise=1000`.
  2. Event `{"event_id": "r1", "type": "refund_processed", "amount_paise": 1000}` is applied (first time: `refunded_paise` becomes 2000).
  3. The identical event `{"event_id": "r1", "type": "refund_processed", "amount_paise": 1000}` is applied again (simulating network retry/duplicate delivery).
- **Expected behaviour**:
  Idempotency check detects that `r1` is already in `processed_event_ids`. The second call is a no-op: `refunded_paise` remains 2000, and `r1` is not duplicated in `processed_event_ids`.
- **Actual observed result**:
  `refunded_paise` is 2000, `payment_status` is `PAID`, and `processed_event_ids` contains `['r1']` once.
- **Test verifying it**:
  `tests/test_contract.py::test_duplicate_refund_event_is_idempotent`.

### Edge Case 3: Late Asynchronous Payment Confirmation on Cancelled Order
- **Input sequence**:
  1. Order `ORD-3` initialized in `PLACED` state with `total_paise=2500`.
  2. Customer cancels immediately before payment webhook arrives: `{"event_id": "c1", "type": "cancel_requested"}`. Order becomes `CANCELLED`, `payment_status="UNPAID"`, `refund_due_paise=0`.
  3. Asynchronous payment gateway confirmation arrives: `{"event_id": "p1", "type": "payment_confirmed"}`.
- **Expected behaviour**:
  Order remains `CANCELLED`. Payment transitions from `UNPAID` to `PAID`. Because the order is already cancelled, full order total (`2500` paise) is allocated to `refund_due_paise` to permit future refund processing.
- **Actual observed result**:
  `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=2500`. Subsequent refund event of 2500 transitions payment status to `REFUNDED`.
- **Test verifying it**:
  `tests/test_contract.py::test_payment_confirmed_after_cancellation_marks_refund_due`.

## 3. Assumptions and limitations
- **Monetary Units**: All amounts are strictly positive integer paise. Sub-paise, negative values, and floating point representations are strictly rejected to ensure financial integrity.
- **Terminal States**:
  - `DELIVERED` is terminal for standard fulfillment; cancellations cannot be initiated post-delivery.
  - `REJECTED` and `CANCELLED` are terminal lifecycle states; once cancelled or rejected, orders cannot be accepted or dispatched.
- **Refund Eligibility**: Refunds can only be issued for orders that have been successfully `PAID` and are in either `CANCELLED` or `REJECTED` status. Active orders (`PLACED`, `ACCEPTED`, `OUT_FOR_DELIVERY`, `DELIVERED`) cannot be refunded through this lifecycle path.
- **Reconciliation Scope**: Reconciliation between internal and external provider records is strictly keyed by string `order_id`. Discrepancies in amounts and discrepancies in statuses are tracked orthogonally without mutual exclusion.
- **Concurrency Limitation**: Current in-memory service functions are thread-confined. In a distributed multi-worker service, database transactions or distributed idempotency keys would be required.
