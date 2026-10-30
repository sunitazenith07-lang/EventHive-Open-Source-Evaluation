# challenges.md — COMPULSORY submission

## 1. Challenge or confusing behaviour
During the investigation and implementation of the OrderOps service, three concrete technical challenges arose:
1. **Separation of Amount and Status Mismatches in Reconciliation**:
   In the original starter implementation of `reconcile_orders`, the code checked:
   ```python
   if a.get("amount_paise") != b.get("amount_paise"):
       report["amount_mismatches"].append(key)
   else:
       report["matched"].append(key)
   ```
   This created two subtle bugs: orders with identical amounts but conflicting lifecycle statuses (e.g., internal `PLACED` vs provider `CANCELLED`) were falsely categorized as `matched`, and orders that differed in *both* amount and status only reported the amount mismatch while completely dropping the status discrepancy.
2. **Refund Safety Under Partial Multi-Step Executions**:
   The starter code blindly executed `out["refunded_paise"] += event.get("amount_paise", 0)` and marked `payment_status = "REFUNDED"` whenever `refunded_paise >= refund_due_paise`. If an order was unpaid, `refund_due_paise` was 0, meaning any refund event of 0 or greater instantly marked an unpaid order as `REFUNDED`. Furthermore, cumulative partial refunds could exceed the order total if multiple partial refund events arrived.
3. **Out-of-Order Asynchronous Webhook Sequence (Payment Arrival Post-Cancellation)**:
   In distributed food-delivery architectures, network latency or asynchronous gateway webhooks can deliver `cancel_requested` before `payment_confirmed`. When the order was cancelled while `payment_status` was `UNPAID`, `refund_due_paise` was correctly initialized to 0. However, when the delayed `payment_confirmed` event arrived subsequently, `payment_status` transitioned to `PAID`, but `refund_due_paise` remained 0, causing subsequent valid refund events to be rejected as exceeding 0 due balance.

## 2. Evidence
- **Assertion Failure in Contract Tests**:
  `test_reconcile_reports_status_difference` failed on the starter code:
  ```
  assert report["status_mismatches"] == ["A"]
  E AssertionError: assert [] == ['A']
  ```
- **Dual Discrepancy Silent Drop**:
  When reconciling an internal record `{"order_id": "A", "amount_paise": 100, "status": "PLACED"}` with a provider record `{"order_id": "A", "amount_paise": 90, "status": "CANCELLED"}`, `report["status_mismatches"]` was empty because the `if/else` branched exclusively to `amount_mismatches`.
- **Invalid Refund Accumulation**:
  In parametrized tests `test_invalid_refund_amounts_are_ignored`, passing `amount_paise = -5000` or `amount_paise = 0.5` corrupted `refunded_paise` because no type or polarity check existed.
- **Idempotency Replay Mutation**:
  Calling `apply_order_event(first, refund_event)` twice when `first` had already processed `refund_event` resulted in double-refunding because refund logic executed prior to checking or ignoring duplicates.

## 3. What I tried
1. **Reconciliation Refactoring**:
   - *Attempt 1*: Added an `elif a.get("status") != b.get("status"): report["status_mismatches"].append(key)`.
   - *Result*: While this caught pure status mismatches, orders with *both* amount and status mismatches still skipped the `elif` branch, failing dual-discrepancy validation.
   - *Attempt 2*: Decoupled the two checks into independent evaluations `amount_mismatch` and `status_mismatch`. Verified with a dedicated unit test asserting both lists contain the order ID.
2. **Refund Guarding & Type Safety**:
   - *Attempt 1*: Checked `if amount > 0 and amount <= due:`.
   - *Result*: In Python, boolean `True` evaluates as integer `1` (`isinstance(True, int) == True`), allowing boolean flags to increment `refunded_paise`. Also floats like `0.5` passed the inequality check.
   - *Attempt 2*: Enforced strict identity checks: `type(amount) is int and amount > 0 and amount <= due - refunded` along with order state validation `out.get("status") in ("CANCELLED", "REJECTED") and out.get("payment_status") == "PAID"`.
3. **Event Ordering Resilience**:
   - *Observation*: Traced lifecycle sequence where `cancel_requested` arrives first, followed by `payment_confirmed`.
   - *Resolution*: Updated `payment_confirmed` handling to inspect `out.get("status")`. If the order is already in `CANCELLED` or `REJECTED`, set `out["refund_due_paise"] = out.get("total_paise", 0)`.

## 4. Resolution
The root causes were resolved by:
1. Writing non-exclusive evaluations in `reconcile_orders`:
   ```python
   amount_mismatch = a.get("amount_paise") != b.get("amount_paise")
   status_mismatch = a.get("status") != b.get("status")
   if amount_mismatch:
       report["amount_mismatches"].append(key)
   if status_mismatch:
       report["status_mismatches"].append(key)
   if not amount_mismatch and not status_mismatch:
       report["matched"].append(key)
   ```
2. Implemented strict eligibility, positive integer type check, and remaining balance arithmetic in `refund_processed`:
   ```python
   amount = event.get("amount_paise")
   due = out.get("refund_due_paise", 0)
   refunded = out.get("refunded_paise", 0)
   if (out.get("status") in ("CANCELLED", "REJECTED")
           and out.get("payment_status") == "PAID"
           and type(amount) is int and amount > 0
           and type(due) is int and due > 0
           and type(refunded) is int and 0 <= refunded <= due
           and amount <= due - refunded):
       out["refunded_paise"] += amount
       if out["refunded_paise"] == due:
           out["payment_status"] = "REFUNDED"
   ```
3. Guarding against malformed events and duplicate `event_id` before modifying any order fields.

## 5. Proof and regression prevention
- **Tests demonstrating the fix**:
  - `test_reconcile_reports_amount_and_status_differences_separately`: Proves dual-discrepancy tracking.
  - `test_refunds_cannot_exceed_due`: Parametrized with 20 distinct boundary pairs verifying cumulative refund caps.
  - `test_duplicate_refund_event_is_idempotent`: Proves replayed refund events do not add incremental paise.
  - `test_payment_confirmed_after_cancellation_marks_refund_due`: Proves out-of-order webhook recovery.
  - `test_malformed_event_is_ignored`: Proves unexpected event structures leave order state intact.
- **Related edge cases tested**:
  - Boolean values (`True`, `False`) passed as `amount_paise` are rejected.
  - Floats and string amounts are rejected without raising unhandled exceptions.
  - Orders in `OUT_FOR_DELIVERY` or `DELIVERED` status ignore `cancel_requested` events.

## 6. Unresolved challenge or next step
- **Concurrency & Distributed Locks**:
  In an offline simulation, events are processed sequentially on in-memory dictionaries. In a production environment with concurrent webhook workers, two simultaneous refund requests could read the same `refunded_paise` and produce a race condition. Production implementations would require database-level row locking (`SELECT FOR UPDATE`), an optimistic concurrency version check (`version_id`), or an event-sourced ledger table with unique event constraints.
