# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
Example lifecycle for order `ORD-9001` (amount: 2500 paise, initial state: `PLACED`, `UNPAID`):

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `{"event_id": "EV-101", "type": "payment_confirmed"}` | Status: `PLACED`, Payment: `PAID`, Due: 0, Refunded: 0, Events: `['EV-101']` | `{'order_id': 'ORD-9001', 'total_paise': 2500, 'status': 'PLACED', 'payment_status': 'PAID', 'refund_due_paise': 0, 'refunded_paise': 0, 'processed_event_ids': ['EV-101']}` |
| 2 | `{"event_id": "EV-102", "type": "restaurant_accepted"}` | Status: `ACCEPTED`, Payment: `PAID`, Due: 0, Refunded: 0, Events: `['EV-101', 'EV-102']` | `{'order_id': 'ORD-9001', 'total_paise': 2500, 'status': 'ACCEPTED', 'payment_status': 'PAID', 'refund_due_paise': 0, 'refunded_paise': 0, 'processed_event_ids': ['EV-101', 'EV-102']}` |
| 3 | `{"event_id": "EV-103", "type": "cancel_requested"}` | Status: `CANCELLED`, Payment: `PAID`, Due: 2500, Refunded: 0, Events: `['EV-101', 'EV-102', 'EV-103']` | `{'order_id': 'ORD-9001', 'total_paise': 2500, 'status': 'CANCELLED', 'payment_status': 'PAID', 'refund_due_paise': 2500, 'refunded_paise': 0, 'processed_event_ids': ['EV-101', 'EV-102', 'EV-103']}` |
| 4 | `{"event_id": "EV-104", "type": "refund_processed", "amount_paise": 1000}` | Status: `CANCELLED`, Payment: `PAID`, Due: 2500, Refunded: 1000, Events: `['EV-101', 'EV-102', 'EV-103', 'EV-104']` | `{'order_id': 'ORD-9001', 'total_paise': 2500, 'status': 'CANCELLED', 'payment_status': 'PAID', 'refund_due_paise': 2500, 'refunded_paise': 1000, 'processed_event_ids': ['EV-101', 'EV-102', 'EV-103', 'EV-104']}` |
| 5 | `{"event_id": "EV-105", "type": "refund_processed", "amount_paise": 1500}` | Status: `CANCELLED`, Payment: `REFUNDED`, Due: 2500, Refunded: 2500, Events: `['EV-101', 'EV-102', 'EV-103', 'EV-104', 'EV-105']` | `{'order_id': 'ORD-9001', 'total_paise': 2500, 'status': 'CANCELLED', 'payment_status': 'REFUNDED', 'refund_due_paise': 2500, 'refunded_paise': 2500, 'processed_event_ids': ['EV-101', 'EV-102', 'EV-103', 'EV-104', 'EV-105']}` |

## 2. Three edge cases

### Edge Case 1: Cancellation Attempt After Order Dispatch
- **Input/Event Sequence:**
  1. Order `ORD-9002` created at `PLACED` with 1500 paise.
  2. `restaurant_accepted` -> transitions to `ACCEPTED`.
  3. `dispatch_started` -> transitions to `OUT_FOR_DELIVERY`.
  4. `cancel_requested` is received while out for delivery.
- **Expected Behaviour:** Cancellation must be rejected once the order has been dispatched. Order status remains `OUT_FOR_DELIVERY`, and no refund is marked due.
- **Actual Observed Result:** Order status remains `OUT_FOR_DELIVERY`, `refund_due_paise` remains 0.
- **Test:** `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` and `tests/test_acceptance_matrix.py::test_order_state_transition_matrix[OUT_FOR_DELIVERY-cancel_requested-OUT_FOR_DELIVERY]`.

### Edge Case 2: Duplicate Refund Event Replay
- **Input/Event Sequence:**
  1. Order `ORD-9003` cancelled with `payment_status="PAID"` and `refund_due_paise=2000`.
  2. Event `{"event_id": "REF-01", "type": "refund_processed", "amount_paise": 1000}` applied.
  3. Replay of identical event `{"event_id": "REF-01", "type": "refund_processed", "amount_paise": 1000}`.
- **Expected Behaviour:** The duplicate event must be discarded via idempotency check on `event_id`. Total refunded amount must remain 1000 paise; event ID must appear only once in `processed_event_ids`.
- **Actual Observed Result:** `refunded_paise == 1000`, `processed_event_ids == ["REF-01"]`.
- **Test:** `tests/test_contract.py::test_replayed_refund_event_does_not_double_refund`.

### Edge Case 3: Out-of-Order Payment Confirmation Following Rejection
- **Input/Event Sequence:**
  1. Order `ORD-9004` created at `PLACED` with 3000 paise, `payment_status="UNPAID"`.
  2. Restaurant rejects the order (`restaurant_rejected`) -> status becomes `REJECTED`, `refund_due_paise` remains 0 because payment was unconfirmed.
  3. Delayed payment gateway notification arrives (`payment_confirmed`).
- **Expected Behaviour:** Order status remains `REJECTED`, payment status transitions to `PAID`, and `refund_due_paise` is automatically set to 3000 paise (`total_paise`) to prevent customer payment from being stranded without refund eligibility.
- **Actual Observed Result:** `status == "REJECTED"`, `payment_status == "PAID"`, `refund_due_paise == 3000`.
- **Test:** `tests/test_contract.py::test_late_payment_confirmed_on_rejected_order`.

## 3. Assumptions and limitations
- **Cancellation Eligibility:** Customer cancellation is only permitted in `PLACED` and `ACCEPTED` stages. Once `dispatch_started` occurs, the order cannot be cancelled by customer request.
- **Dispatch Flow:** Orders must follow sequential progression (`PLACED -> ACCEPTED -> OUT_FOR_DELIVERY -> DELIVERED`). Dispatches directly from `PLACED` or deliveries directly from `ACCEPTED` are ignored.
- **Monetary Unit:** All values represent non-negative integer paise. Floats, negative values, and non-numeric types are discarded.
- **Refund Invariants:** Refunds apply exclusively to paid orders that are in `REJECTED` or `CANCELLED` status. Cumulative refunds cannot exceed `refund_due_paise`.
- **Concurrency Limitation:** In-memory dictionary manipulation is synchronous; distributed production environments would require distributed locking or optimistic concurrency control on order versions.
