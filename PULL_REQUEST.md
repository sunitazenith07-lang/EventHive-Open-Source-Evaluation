# Pull Request: Fix Order Lifecycle, Event Idempotency, Refund Safety, and Reconciliation

**Target Repository:** `sunitazenith07-lang/OrderOps-Open-Source-Evaluation`  
**Base Branch:** `main`  
**Head Branch:** `fix/order-lifecycle-refund-reconciliation` (or `main`)  

---

## What did you change?
1. **Event Idempotency:** Implemented deduplication on `event_id` in `apply_order_event()`. Replaying any previously processed event now returns the order state unmodified without appending duplicate event IDs.
2. **Refund Safety & Eligibility:**
   - Restricted refunds exclusively to paid orders that have been cancelled or rejected (`status in ("REJECTED", "CANCELLED") and payment_status == "PAID" and refund_due_paise > 0`).
   - Added strict type checking for positive integer paise (`isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`), explicitly preventing Python booleans (`True`/`False`), floats, and strings from mutating balances.
   - Enforced maximum refund limits against outstanding refundable amounts (`amount <= refund_due_paise - refunded_paise`).
   - Preserved `payment_status="PAID"` on partial refunds, transitioning to `"REFUNDED"` only when the full due amount has been processed.
   - Corrected out-of-order payment confirmation arriving after restaurant rejection or customer cancellation so that `refund_due_paise` correctly reflects `total_paise`.
3. **Reconciliation Engine:**
   - Added status comparison logic (`a_status != b_status`) to correctly populate `status_mismatches`.
   - Unified key lookups across internal models (`total_paise`) and provider settlement reports (`amount_paise`), fixing false-positive amount mismatches in the demo.
   - Handled orders exhibiting both amount and status mismatches by reporting them deterministically in both categories.
4. **Stretch Feature:**
   - Implemented `export_awaiting_refund_csv(orders, filepath=None)` to export orders with outstanding refund balances to CSV.
5. **Regression & Edge Case Tests:**
   - Added 10 comprehensive tests in `tests/test_regression_and_edge_cases.py`.

## Root cause
- **Idempotency Defect:** `service.py` appended every incoming `event_id` to `processed_event_ids` at the end of `apply_order_event()` without checking for prior existence, causing event replay tests to fail on duplicate entries and state mutations.
- **Refund Processing Defect:** `service.py` incremented `refunded_paise` without verifying order status, payment status, non-boolean integer type, or remaining refundable capacity.
- **Reconciliation Defect:** `service.py` compared only `a.get("amount_paise") != b.get("amount_paise")`, which returned `None` for internal orders using `total_paise`, and completely lacked status difference checks in its fallback branch.

## Tests
- [x] I ran `python -m pytest -q`.
- [x] I added or updated regression tests for my change.
- [x] I did not delete, skip, weaken or bypass existing tests.

**Test Summary:**
- Baseline: `62 failed, 150 passed in 0.64s` (Total 212 tests)
- After Fixes & Regression Suite: `222 passed in 0.33s` (Total 222 tests, 0 failures, 100% pass rate)
- Offline Demo (`python -m main`):
  ```
  matched: ['ORD-101']
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: []
  status_mismatches: ['ORD-102']
  ```

## Required problem-solving documents (all three mandatory; 15 marks total)
- [x] `approach.md` completed (5 marks).
- [x] `challenges.md` completed (COMPULSORY; 5 marks).
- [x] `optimizations.md` completed (5 marks).

**Key insights from documents:**
- `approach.md`: Details how baseline failures were categorized into 3 core defects, the hypothesis-driven fixes chosen, and verification results.
- `challenges.md`: Details how Python's `bool` subtyping `int` caused `True` to pass standard integer checks, and how schema key differences (`total_paise` vs `amount_paise`) were systematically resolved.
- `optimizations.md`: Evaluated early-return idempotency exits, $O(N \log N)$ hash-map reconciliation, and micro-benchmark trade-offs between `copy.deepcopy` and shallow copy.

## Edge cases checked
1. **Replay of events across all types:** Duplicate events (`payment_confirmed`, `restaurant_accepted`, `cancel_requested`, `refund_processed`) return the order unmodified without duplicate `processed_event_ids`.
2. **Post-dispatch cancellation:** Orders in `OUT_FOR_DELIVERY` or `DELIVERED` status ignore cancellation requests and retain `refund_due_paise=0`.
3. **Boolean / Float refund payloads:** Payloads with `amount_paise=True`, `False`, `None`, `-10`, `0.5`, or strings are rejected; `refunded_paise` remains 0.
4. **Multiple partial refunds:** Incremental refunds remain `PAID` until cumulative `refunded_paise` reaches `refund_due_paise`, transitioning to `REFUNDED`. Excess amounts are rejected.
5. **Reconciliation dual mismatch:** Orders differing in both amount and status are placed into both `amount_mismatches` and `status_mismatches`, and excluded from `matched`.

## Design decisions / limitations
- **Assumptions:** All currency amounts are strictly non-negative integer paise. Cancellations are only valid before dispatch (`PLACED` or `ACCEPTED`).
- **Limitations:** Events without an `event_id` cannot be tracked by the idempotency deduplicator. Reconciliation assumes unique order IDs per input list.
- **Challenge-specific notes:** Full flow documentation and walkthrough examples are provided in `ORDER_FLOW_NOTES.md`, `TESTING.md`, `ARCHITECTURE.md`, and `PROGRESS_REPORT.md`.

## Integrity confirmation
- [x] This is my own individual work.
- [x] I have followed the evaluation's AI-use policy.
- [x] I can explain my changes and make a small live modification if asked.
