# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
List the events in order, the expected state after each event, and the actual state your implementation returns.

**Scenario:** Customer places order `ORD-7701` for ₹550.00 (`total_paise = 55000`). Payment confirms, restaurant accepts, customer cancels before dispatch, followed by a partial refund and then the remaining refund.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 0 | Initial State: `new_order("ORD-7701", 55000)` | `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]` | `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=[]` |
| 1 | `ev("EV-1", "payment_confirmed")` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1"]` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1"]` |
| 2 | `ev("EV-2", "restaurant_accepted")` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2"]` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2"]` |
| 3 | `ev("EV-3", "cancel_requested")` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=55000`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2", "EV-3"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=55000`, `refunded_paise=0`, `processed_event_ids=["EV-1", "EV-2", "EV-3"]` |
| 4 | `ev("EV-4", "refund_processed", amount_paise=20000)` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=55000`, `refunded_paise=20000`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=55000`, `refunded_paise=20000`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4"]` |
| 5 | `ev("EV-5", "refund_processed", amount_paise=35000)` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=55000`, `refunded_paise=55000`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4", "EV-5"]` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=55000`, `refunded_paise=55000`, `processed_event_ids=["EV-1", "EV-2", "EV-3", "EV-4", "EV-5"]` |

## 2. Three edge cases
For each, state the input/event sequence, expected behaviour, actual observed result, and test that verifies it.

### Edge Case 1: Post-Dispatch Cancellation Attempt
- **Input / Event Sequence:**
  1. Order `ORD-DISP` placed (`status="PLACED"`, `total_paise=40000`).
  2. `payment_confirmed` -> `payment_status="PAID"`.
  3. `restaurant_accepted` -> `status="ACCEPTED"`.
  4. `dispatch_started` -> `status="OUT_FOR_DELIVERY"`.
  5. `cancel_requested` arrives while rider is delivering.
- **Expected Behaviour:**
  The cancellation request must be ignored. The order must remain `status="OUT_FOR_DELIVERY"`, `payment_status` remains `PAID`, and `refund_due_paise` remains `0`. Under no circumstances should the order transition to `CANCELLED` once dispatched.
- **Actual Observed Result:**
  Order status remained `OUT_FOR_DELIVERY`; `refund_due_paise` stayed `0`.
- **Verifying Test:**
  `test_cancel_after_dispatch_is_ignored` and `test_cannot_cancel_out_for_delivery_or_delivered`.

### Edge Case 2: Out-of-Order Payment Confirmation Following Restaurant Rejection
- **Input / Event Sequence:**
  1. Order `ORD-REJ` placed (`status="PLACED"`, `total_paise=32000`, `payment_status="UNPAID"`).
  2. `restaurant_rejected` arrives before payment confirmation callback -> `status="REJECTED"`, `refund_due_paise=0` (since payment was not yet confirmed).
  3. Delayed payment gateway callback `payment_confirmed` arrives.
- **Expected Behaviour:**
  Upon receiving `payment_confirmed` for an already-rejected order, the system must set `payment_status="PAID"` and immediately recognize that a refund is due by setting `refund_due_paise=32000` (the full order total). Subsequent valid `refund_processed` events can then successfully disburse the funds.
- **Actual Observed Result:**
  `payment_status` transitioned to `PAID` and `refund_due_paise` was set to `32000`. Full refund event subsequently transitioned order to `REFUNDED`.
- **Verifying Test:**
  `test_payment_confirmed_after_rejection_sets_refund_due`.

### Edge Case 3: Replay and Excess Refund Protection
- **Input / Event Sequence:**
  1. Order `ORD-REF-PROT` cancelled after payment (`total_paise=5000`, `payment_status="PAID"`, `refund_due_paise=5000`).
  2. Partial refund event `ev("R-10", "refund_processed", amount_paise=3000)` arrives.
  3. Replay of event `ev("R-10", "refund_processed", amount_paise=3000)` arrives via network duplicate.
  4. Second refund event `ev("R-11", "refund_processed", amount_paise=2500)` arrives (attempting to refund 2500 when only 2000 remains).
- **Expected Behaviour:**
  Step 2 processes 3000 paise refund (`refunded_paise=3000`, `payment_status="PAID"`).
  Step 3 (replay of `R-10`) is detected by idempotency on `event_id` and rejected with zero state alteration.
  Step 4 attempts to disburse 2500 paise, exceeding the remaining 2000 balance (`5000 - 3000 = 2000`), and must be ignored entirely, leaving `refunded_paise=3000`.
- **Actual Observed Result:**
  `R-10` replay produced no state changes; `R-11` over-refund was safely ignored; `refunded_paise` remained strictly at 3000 paise.
- **Verifying Test:**
  `test_idempotency_across_different_event_types`, `test_refunds_cannot_exceed_due`, `test_multiple_partial_refunds_reaching_exact_total`.

## 3. Assumptions and limitations
Document assumptions about cancellation eligibility, dispatch transitions, refund due/refunded amounts, and any unresolved issue.

1. **Cancellation Eligibility:**
   - Cancellations are permitted strictly while an order is in `PLACED` or `ACCEPTED` status.
   - Once an order transitions to `OUT_FOR_DELIVERY` or `DELIVERED`, cancellation requests are strictly ignored to protect delivery partners and restaurants from inventory loss.

2. **Dispatch & Lifecycle Transitions:**
   - Orders can only move from `PLACED` to `ACCEPTED` or `REJECTED`.
   - Dispatch can only start (`OUT_FOR_DELIVERY`) from `ACCEPTED`.
   - Delivery (`DELIVERED`) can only occur from `OUT_FOR_DELIVERY`.
   - Rejection and cancellation are terminal order lifecycle states.

3. **Refund Amounts & Currencies:**
   - All financial amounts are integer paise (1 INR = 100 paise) to prevent floating-point rounding errors.
   - Negative amounts, 0, floats, strings, and booleans (`True`/`False`) are rejected as invalid payloads.
   - Refund amounts cannot exceed outstanding refundable amounts (`refund_due_paise - refunded_paise`).

4. **Idempotency Scope:**
   - Idempotency is enforced by tracking unique `event_id` values in `processed_event_ids`.
   - Replaying any event with an already-seen `event_id` returns the current state unmodified.
   - Events lacking an `event_id` cannot be deduplicated; upstream event producers must guarantee non-null `event_id` for idempotency tracking.

5. **Reconciliation Semantics:**
   - Reconciliation matches orders keyed on `order_id`.
   - Internal records support both `amount_paise` and `total_paise` keys.
   - When an order exhibits both amount and status discrepancies between internal and provider records, it is reported in both `amount_mismatches` and `status_mismatches` to provide full visibility to operations teams.
