# ORDER_FLOW_NOTES.md — Order Lifecycle, State Flow & Edge Cases

## 1. Example Order-Event Sequence (Expected vs. Actual State)
Below is a complete trace for order `ORD-500` initialized via `new_order("ORD-500", 1000)` (`total_paise = 1000`), demonstrating payment confirmation, restaurant acceptance, pre-dispatch customer cancellation, a duplicate cancellation replay, a partial refund, an invalid over-refund attempt, and the final completing refund.

| Step | Event Applied | Expected State (`status`, `payment_status`, `refund_due_paise`, `refunded_paise`, `processed_event_ids`) | Actual State Produced by `apply_order_event` |
|---|---|---|---|
| 0 (Init) | `new_order("ORD-500", 1000)` | `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `ids=[]` | `status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`, `ids=[]` |
| 1 | `{"event_id": "E1", "type": "payment_confirmed"}` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `ids=["E1"]` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `ids=["E1"]` |
| 2 | `{"event_id": "E2", "type": "restaurant_accepted"}` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `ids=["E1", "E2"]` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `ids=["E1", "E2"]` |
| 3 | `{"event_id": "E3", "type": "cancel_requested"}` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=1000`, `refunded_paise=0`, `ids=["E1", "E2", "E3"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=1000`, `refunded_paise=0`, `ids=["E1", "E2", "E3"]` |
| 4 | `{"event_id": "E3", "type": "cancel_requested"}` (Duplicate Replay) | No state mutation; `ids=["E1", "E2", "E3"]` | No state mutation; `ids=["E1", "E2", "E3"]` |
| 5 | `{"event_id": "E4", "type": "refund_processed", "amount_paise": 400}` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=1000`, `refunded_paise=400`, `ids=["E1", "E2", "E3", "E4"]` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=1000`, `refunded_paise=400`, `ids=["E1", "E2", "E3", "E4"]` |
| 6 | `{"event_id": "E5", "type": "refund_processed", "amount_paise": 700}` (Exceeds remaining 600 due) | Refund rejected; `payment_status="PAID"`, `refunded_paise=400`, `ids=["E1", "E2", "E3", "E4", "E5"]` | Refund rejected; `payment_status="PAID"`, `refund_due_paise=1000`, `refunded_paise=400`, `ids=["E1", "E2", "E3", "E4", "E5"]` |
| 7 | `{"event_id": "E6", "type": "refund_processed", "amount_paise": 600}` (Completes remaining 600 due) | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=1000`, `refunded_paise=1000`, `ids=["E1", "E2", "E3", "E4", "E5", "E6"]` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=1000`, `refunded_paise=1000`, `ids=["E1", "E2", "E3", "E4", "E5", "E6"]` |

## 2. Assumptions
1. **Strict State Machine Guards:**
   - `restaurant_accepted` and `restaurant_rejected` are valid only from `PLACED`.
   - `cancel_requested` is valid only from `PLACED` or `ACCEPTED`. Once `dispatch_started` transitions an order from `ACCEPTED` to `OUT_FOR_DELIVERY`, any subsequent `cancel_requested` is ignored.
   - `order_delivered` is valid only from `OUT_FOR_DELIVERY`.
2. **Idempotency via `event_id`:**
   - Any event carrying a non-empty, non-boolean `event_id` already present in `processed_event_ids` is treated as a duplicate replay and returns the copied order unchanged.
   - Events missing an `event_id` (`None` or `""`) are evaluated without appending an invalid ID to `processed_event_ids`.
3. **Integer Paise & Refund Eligibility:**
   - All monetary values (`total_paise`, `refund_due_paise`, `refunded_paise`, `amount_paise`) must be strict Python `int` instances (`not isinstance(val, bool)`).
   - Refunds apply only when `status in ("REJECTED", "CANCELLED")`, `payment_status == "PAID"`, and `refund_due_paise > 0`.
4. **Reconciliation Field Normalization:**
   - Internal orders may store their total under `total_paise` (as produced by `models.new_order`) or `amount_paise` (as used in unit test fixtures). `reconcile_orders` checks `amount_paise` first and falls back to `total_paise`.

## 3. Edge Cases Analyzed
1. **Post-Dispatch Cancellation Attempt (`cancel_requested` on `OUT_FOR_DELIVERY`):**
   - *Scenario:* Customer requests cancellation after rider dispatch has started.
   - *Handling:* `apply_order_event` ignores `cancel_requested` because `status` is not in `("PLACED", "ACCEPTED")`. The order remains `OUT_FOR_DELIVERY` and `refund_due_paise` stays `0` (verified by `test_cancel_after_dispatch_is_ignored`).
2. **Late Payment Confirmation After Restaurant Rejection (`restaurant_rejected` -> `payment_confirmed`):**
   - *Scenario:* Restaurant rejects an order at `PLACED` while `payment_status` is still `UNPAID`, and the payment gateway webhook (`payment_confirmed`) arrives shortly afterward.
   - *Handling:* When `payment_confirmed` transitions `payment_status` from `UNPAID` to `PAID` on an order whose status is already `REJECTED` or `CANCELLED`, `refund_due_paise` is automatically set to `total_paise` so the customer can be refunded (verified by `test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due`).
3. **Simultaneous Amount and Status Mismatch in Reconciliation:**
   - *Scenario:* Internal record has `total_paise=5000, status="ACCEPTED"` while provider record has `amount_paise=4500, status="CANCELLED"`.
   - *Handling:* `reconcile_orders` evaluates amount and status differences independently, recording the `order_id` in both `amount_mismatches` and `status_mismatches` while excluding it from `matched` (verified by `test_reconcile_handles_total_paise_and_simultaneous_amount_and_status_mismatch`).
4. **Boolean & Non-Integer Refund Payloads (`amount_paise=True` or `0.5`):**
   - *Scenario:* A malformed event passes `amount_paise=True` (which satisfies `isinstance(True, int)` in Python) or a float `0.5`.
   - *Handling:* `_is_strict_int` explicitly excludes booleans and non-integers, leaving `refunded_paise` unchanged (verified by `test_boolean_and_non_integer_refund_amounts_rejected`).
