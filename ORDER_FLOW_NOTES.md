# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
Below is a real order lifecycle trace for an order with total amount 5000 paise (₹50.00) experiencing payment confirmation, acceptance, cancellation, and subsequent partial and final refund.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` (EV-101) | `status: "PLACED"`, `payment_status: "PAID"`, `refund_due: 0`, `refunded: 0`, `events: ["EV-101"]` | `{"status": "PLACED", "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0, "processed_event_ids": ["EV-101"]}` |
| 2 | `restaurant_accepted` (EV-102) | `status: "ACCEPTED"`, `payment_status: "PAID"`, `refund_due: 0`, `refunded: 0`, `events: ["EV-101", "EV-102"]` | `{"status": "ACCEPTED", "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0, "processed_event_ids": ["EV-101", "EV-102"]}` |
| 3 | `cancel_requested` (EV-103) | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due: 5000`, `refunded: 0`, `events: ["EV-101", "EV-102", "EV-103"]` | `{"status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 5000, "refunded_paise": 0, "processed_event_ids": ["EV-101", "EV-102", "EV-103"]}` |
| 4 | `refund_processed` (EV-104, amount: 2000) | `status: "CANCELLED"`, `payment_status: "PAID"`, `refund_due: 5000`, `refunded: 2000`, `events: ["EV-101", "EV-102", "EV-103", "EV-104"]` | `{"status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 5000, "refunded_paise": 2000, "processed_event_ids": ["EV-101", "EV-102", "EV-103", "EV-104"]}` |
| 5 | `refund_processed` (EV-105, amount: 3000) | `status: "CANCELLED"`, `payment_status: "REFUNDED"`, `refund_due: 5000`, `refunded: 5000`, `events: ["EV-101", "EV-102", "EV-103", "EV-104", "EV-105"]` | `{"status": "CANCELLED", "payment_status": "REFUNDED", "refund_due_paise": 5000, "refunded_paise": 5000, "processed_event_ids": ["EV-101", "EV-102", "EV-103", "EV-104", "EV-105"]}` |

## 2. Three edge cases

### 1. Cancellation Attempt After Dispatch
- **Input sequence:**
  1. `order = new_order("ORD-E1", 4500, "PLACED")`
  2. `payment_confirmed` (EV-1)
  3. `restaurant_accepted` (EV-2)
  4. `dispatch_started` (EV-3) -> Transitions to `OUT_FOR_DELIVERY`
  5. `cancel_requested` (EV-4)
- **Expected behaviour:** The cancellation is rejected because the order has already been dispatched. The status remains `OUT_FOR_DELIVERY`, and `refund_due_paise` remains 0.
- **Actual observed result:** `status` remained `OUT_FOR_DELIVERY`, `payment_status` remained `PAID`, `refund_due_paise` was 0.
- **Test that verifies it:** `test_cancellation_after_dispatch_preserves_state` in `tests/test_regression_edge_cases.py` and `test_cancel_after_dispatch_is_ignored` in `tests/test_contract.py`.

### 2. Duplicate Event Replay With Conflicting Payload
- **Input sequence:**
  1. `order = new_order("ORD-E2", 5000, "CANCELLED")` with `payment_status="PAID"`, `refund_due_paise=5000`
  2. `refund_processed` with `event_id="R-100"` and `amount_paise=2500`
  3. `refund_processed` replay with same `event_id="R-100"` but modified `amount_paise=5000`
- **Expected behaviour:** Idempotency catches `event_id="R-100"` on the second call. The second event is discarded immediately, preserving the original refund amount of 2500 paise and keeping `processed_event_ids` deduplicated.
- **Actual observed result:** Order retained `refunded_paise: 2500` and `processed_event_ids: ["R-100"]`.
- **Test that verifies it:** `test_replay_with_conflicting_payload_is_ignored` in `tests/test_regression_edge_cases.py`.

### 3. Out-of-Order Late Payment Arrival on Rejected Order
- **Input sequence:**
  1. `order = new_order("ORD-E3", 6000, "PLACED")`
  2. `restaurant_rejected` (EV-REJ) -> Order transitions to `REJECTED`, but `refund_due_paise` is 0 because `payment_status` was `UNPAID`.
  3. `payment_confirmed` (EV-PAY) arrives late from payment gateway webhook.
- **Expected behaviour:** Late payment sets `payment_status` to `PAID` and retroactively calculates `refund_due_paise = total_paise` (6000), allowing the customer to be refunded.
- **Actual observed result:** `order["payment_status"] == "PAID"`, `order["status"] == "REJECTED"`, `order["refund_due_paise"] == 6000`.
- **Test that verifies it:** `test_payment_confirmed_after_rejection` in `tests/test_regression_edge_cases.py`.

## 3. Assumptions and limitations
- **Cancellation Eligibility:** Cancellations are only permitted while the order is in `PLACED` or `ACCEPTED` states. Once `dispatch_started` occurs (`OUT_FOR_DELIVERY` or `DELIVERED`), cancellations are strictly disallowed.
- **Refund Eligibility:** Refunds can only be processed if the order is in `REJECTED` or `CANCELLED` status, has a `PAID` payment status, and has an outstanding balance (`refund_due_paise > refunded_paise`).
- **Partial vs. Full Refunds:** Partial refunds keep the payment status as `PAID`. Only when cumulative `refunded_paise` reaches or exceeds `refund_due_paise` does `payment_status` transition to `REFUNDED`.
- **Idempotency Scope:** Idempotency is enforced strictly when `event_id` is supplied. If an event is missing an `event_id`, it is executed once, but cannot be deduplicated if resent.
- **Currency Format:** All financial amounts are integer paise (₹1.00 = 100 paise). Floating-point amounts and booleans are treated as invalid and discarded to prevent financial inaccuracies.
