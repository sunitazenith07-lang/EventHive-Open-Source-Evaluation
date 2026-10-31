# ORDER_FLOW_NOTES.md — Challenge-Specific Order Flow Documentation

## 1. Example Order-Event Sequence
Below is an end-to-end trace of an order created with total 5,000 paise (₹50.00), paid, cancelled prior to dispatch, followed by a partial refund and full refund completion:

**Initial Order State:**
```python
{"order_id": "ORD-7001", "total_paise": 5000, "status": "PLACED", "payment_status": "UNPAID", "refund_due_paise": 0, "refunded_paise": 0, "processed_event_ids": []}
```

| Step | Event | Expected Order / Payment / Refund State | Actual Result |
|---|---|---|---|
| 1 | `{"event_id": "E1", "type": "payment_confirmed"}` | `status="PLACED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["E1"]` | Matches expected exactly |
| 2 | `{"event_id": "E2", "type": "restaurant_accepted"}` | `status="ACCEPTED"`, `payment_status="PAID"`, `refund_due_paise=0`, `refunded_paise=0`, `processed_event_ids=["E1", "E2"]` | Matches expected exactly |
| 3 | `{"event_id": "E3", "type": "cancel_requested"}` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=5000`, `refunded_paise=0`, `processed_event_ids=["E1", "E2", "E3"]` | Matches expected exactly |
| 4 | `{"event_id": "E4", "type": "refund_processed", "amount_paise": 2000}` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=5000`, `refunded_paise=2000`, `processed_event_ids=["E1", "E2", "E3", "E4"]` | Matches expected exactly |
| 5 | `{"event_id": "E5", "type": "refund_processed", "amount_paise": 3000}` | `status="CANCELLED"`, `payment_status="REFUNDED"`, `refund_due_paise=5000`, `refunded_paise=5000`, `processed_event_ids=["E1", "E2", "E3", "E4", "E5"]` | Matches expected exactly |

---

## 2. Three Edge Cases

### Edge Case 1: Cancellation Attempt Arriving After Order Dispatch
- **Input / Event Sequence:**
  1. Order `O-DISPATCH` is in `ACCEPTED` state with `payment_status="PAID"`.
  2. Event `{"event_id": "D1", "type": "dispatch_started"}` transitions state to `OUT_FOR_DELIVERY`.
  3. Customer sends `{"event_id": "C1", "type": "cancel_requested"}`.
- **Expected Behaviour:**
  Cancellation request must be rejected. The order must remain `status="OUT_FOR_DELIVERY"` and `refund_due_paise=0`.
- **Actual Observed Result:**
  Order remains in `status="OUT_FOR_DELIVERY"`, payment status remains `PAID`, refund due remains `0`.
- **Test Verifying It:**
  `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` and `tests/test_regression.py::test_cancellation_after_dispatch_is_safely_ignored`.

### Edge Case 2: Replay of Processed Event with Conflicting Payload (Idempotency)
- **Input / Event Sequence:**
  1. Order `O-REPLAY` has `status="PLACED"`.
  2. Event `{"event_id": "EV-99", "type": "payment_confirmed"}` transitions `payment_status="PAID"`.
  3. Replay event arrives with identical `event_id`: `{"event_id": "EV-99", "type": "restaurant_accepted"}`.
- **Expected Behaviour:**
  Because `event_id` `"EV-99"` was already processed, the duplicate event must be completely ignored. Order status must remain `PLACED`, not transition to `ACCEPTED`, and `processed_event_ids` must not duplicate `"EV-99"`.
- **Actual Observed Result:**
  Order status remains `PLACED`, `payment_status="PAID"`, `processed_event_ids=["EV-99"]`.
- **Test Verifying It:**
  `tests/test_regression.py::test_duplicate_event_payload_conflict_is_ignored` and `tests/test_acceptance_matrix.py::test_payment_event_replay_idempotent`.

### Edge Case 3: Late Payment Confirmation on Already Cancelled or Rejected Order
- **Input / Event Sequence:**
  1. Order `O-LATE` is placed with `payment_status="UNPAID"`.
  2. Restaurant rejects order: `{"event_id": "R1", "type": "restaurant_rejected"}` -> `status="REJECTED"`, `refund_due_paise=0`.
  3. Customer's asynchronous payment arrives late: `{"event_id": "P1", "type": "payment_confirmed"}`.
- **Expected Behaviour:**
  Payment status updates to `"PAID"`. Because the order is already in `REJECTED` status, the full `total_paise` must now be marked as `refund_due_paise` so the customer can be refunded.
- **Actual Observed Result:**
  `payment_status` becomes `"PAID"`, `refund_due_paise` is updated to `total_paise`, and subsequent refund events can be successfully processed.
- **Test Verifying It:**
  `tests/test_regression.py::test_late_payment_confirmed_after_rejection_or_cancellation`.

---

## 3. Assumptions and Limitations
1. **Cancellation Eligibility:**
   Cancellation is only permitted while the order is in `PLACED` or `ACCEPTED` status. Once dispatched (`OUT_FOR_DELIVERY`) or delivered (`DELIVERED`), cancellation requests are strictly ignored to avoid delivery conflicts.
2. **Refund Rules and Boundaries:**
   - Refunds apply exclusively to orders that are in `REJECTED` or `CANCELLED` status and have `payment_status == "PAID"`.
   - Refund amounts must be positive integer paise (`isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`).
   - The refund amount cannot exceed `refund_due_paise - refunded_paise`. If an amount exceeds this, the event is ignored without partial deduction.
   - `payment_status` transitions from `"PAID"` to `"REFUNDED"` only upon full refund reconciliation (`refunded_paise == refund_due_paise`).
3. **Idempotency Scope:**
   - Idempotency is tracked per order via `processed_event_ids`. An event with an existing `event_id` is silently treated as a no-op.
   - Events lacking an `event_id` are processed safely, but cannot be deduplicated by ID.
4. **Reconciliation Invariants:**
   - Reconciliation is deterministic and orders are sorted lexicographically by `order_id`.
   - Records with discrepancies in both amount and status are reported in both `amount_mismatches` and `status_mismatches`.
