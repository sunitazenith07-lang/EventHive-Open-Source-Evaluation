# ORDER_FLOW_NOTES.md — Required Submission

## 1. Example order-event sequence
Below is an end-to-end event sequence for an order (`ORD-501`) with a total value of ₹650.00 (65,000 paise). It illustrates customer payment, restaurant acceptance, pre-dispatch cancellation, and two-stage refund settlement.

| Step | Event Received | Expected State (Status / Payment / Due / Refunded) | Actual Implementation Result |
|---|---|---|---|
| 0 | Initial Creation | `status: PLACED`<br/>`payment_status: UNPAID`<br/>`refund_due_paise: 0`<br/>`refunded_paise: 0` | `{"status": "PLACED", "payment_status": "UNPAID", "refund_due_paise": 0, "refunded_paise": 0}` |
| 1 | `payment_confirmed` (`event_id: "EV-01"`) | `status: PLACED`<br/>`payment_status: PAID`<br/>`refund_due_paise: 0`<br/>`refunded_paise: 0`<br/>`processed: ["EV-01"]` | `{"status": "PLACED", "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0, "processed_event_ids": ["EV-01"]}` |
| 2 | `restaurant_accepted` (`event_id: "EV-02"`) | `status: ACCEPTED`<br/>`payment_status: PAID`<br/>`refund_due_paise: 0`<br/>`refunded_paise: 0`<br/>`processed: ["EV-01", "EV-02"]` | `{"status": "ACCEPTED", "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0, "processed_event_ids": ["EV-01", "EV-02"]}` |
| 3 | `cancel_requested` (`event_id: "EV-03"`) | `status: CANCELLED`<br/>`payment_status: PAID`<br/>`refund_due_paise: 65000`<br/>`refunded_paise: 0`<br/>`processed: ["EV-01", "EV-02", "EV-03"]` | `{"status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 65000, "refunded_paise": 0, "processed_event_ids": ["EV-01", "EV-02", "EV-03"]}` |
| 4 | `refund_processed` (`event_id: "EV-04"`, `amount_paise: 30000`) | `status: CANCELLED`<br/>`payment_status: PAID` (partial)<br/>`refund_due_paise: 65000`<br/>`refunded_paise: 30000`<br/>`processed: [..."EV-04"]` | `{"status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 65000, "refunded_paise": 30000, "processed_event_ids": [..."EV-04"]}` |
| 5 | `refund_processed` (`event_id: "EV-05"`, `amount_paise: 35000`) | `status: CANCELLED`<br/>`payment_status: REFUNDED` (complete)<br/>`refund_due_paise: 65000`<br/>`refunded_paise: 65000`<br/>`processed: [..."EV-05"]` | `{"status": "CANCELLED", "payment_status": "REFUNDED", "refund_due_paise": 65000, "refunded_paise": 65000, "processed_event_ids": [..."EV-05"]}` |

---

## 2. Three edge cases

### Edge Case 1: Cancellation Requested After Dispatch Started
- **Input/Event Sequence:**
  1. `order = new_order("ORD-E1", 45000, "ACCEPTED")` with `payment_status="PAID"`.
  2. Event `dispatch_started` (`"EV-D1"`): Order moves to `OUT_FOR_DELIVERY`.
  3. Event `cancel_requested` (`"EV-C1"`): Customer requests cancellation while delivery partner is in transit.
- **Expected Behaviour:**
  Cancellation is denied after dispatch. Order status remains `OUT_FOR_DELIVERY`, and `refund_due_paise` remains `0`.
- **Actual Observed Result:**
  `status` stayed `OUT_FOR_DELIVERY`, `payment_status` stayed `PAID`, `refund_due_paise` stayed `0`.
- **Test Verifying It:**
  `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` and `tests/test_acceptance_matrix.py::test_order_state_transition_matrix[OUT_FOR_DELIVERY-cancel_requested-OUT_FOR_DELIVERY]`.

### Edge Case 2: Asynchronous Payment Clearing on an Already Rejected Order
- **Input/Event Sequence:**
  1. `order = new_order("ORD-E2", 30000, "PLACED")` with `payment_status="UNPAID"`.
  2. Event `restaurant_rejected` (`"EV-R1"`): Restaurant rejects before payment webhook completes. Status becomes `REJECTED`, `refund_due_paise` remains `0` (since unpaid).
  3. Delayed Event `payment_confirmed` (`"EV-P1"`): Payment gateway webhook confirms customer was charged.
- **Expected Behaviour:**
  Status remains `REJECTED`, `payment_status` updates to `PAID`, and `refund_due_paise` is immediately set to full `total_paise` (30,000 paise) so the system initiates a refund.
- **Actual Observed Result:**
  `status == 'REJECTED'`, `payment_status == 'PAID'`, `refund_due_paise == 30000`.
- **Test Verifying It:**
  `tests/test_regression_and_edge_cases.py::test_late_payment_confirmed_on_rejected_order_sets_refund_due`.

### Edge Case 3: Replay of Cumulative Refund Exceeding Outstanding Balance
- **Input/Event Sequence:**
  1. Order cancelled and paid with `total_paise=5000`, `refund_due_paise=5000`.
  2. Event `refund_processed` (`"EV-RF1"`, `amount_paise=3000`) succeeds (`refunded_paise=3000`).
  3. Duplicate or erroneous Event `refund_processed` (`"EV-RF2"`, `amount_paise=2001`) arrives.
- **Expected Behaviour:**
  Outstanding refundable amount is $5000 - 3000 = 2000$ paise. The incoming amount of 2001 paise exceeds the outstanding balance by 1 paise. The event must be rejected without altering `refunded_paise` or `payment_status`.
- **Actual Observed Result:**
  `refunded_paise` remained `3000`, `payment_status` remained `PAID`.
- **Test Verifying It:**
  `tests/test_regression_and_edge_cases.py::test_refund_exceeding_remaining_due_is_rejected` and `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due[3000-2000]`.

---

## 3. Assumptions and limitations
- **Cancellation Eligibility:**
  - Orders may be cancelled by the customer only while in `PLACED` or `ACCEPTED` status. Once `dispatch_started` has transitioned the order to `OUT_FOR_DELIVERY`, cancellations are rejected. Delivery partner is already on route.
- **Refund Eligibility & Calculation:**
  - Only orders with terminal failure states (`REJECTED` or `CANCELLED`) and confirmed payment (`payment_status == "PAID"`) are eligible for refund processing.
  - Refund amounts must be positive integers representing Indian paise. Booleans, strings, floats, and negative numbers are invalid.
  - Partial refunds are supported and cumulative. `payment_status` remains `PAID` until `refunded_paise >= refund_due_paise`, at which point it transitions to `REFUNDED`.
- **Reconciliation Assumptions:**
  - Reconciliation matches by `order_id`. If an order has different amounts between internal and provider records, it is reported under `amount_mismatches`. If it has different statuses, it is reported under `status_mismatches`. If both differ, it appears in both lists.
  - Matching orders must agree on both amount and status.
- **Limitations:**
  - Out-of-order delivery events (e.g. `order_delivered` arriving before `dispatch_started`) are rejected by state guards. In actual physical operations, human delivery drivers may mark delivery out-of-sequence; handling this would require driver geo-fencing or OTP verification.
