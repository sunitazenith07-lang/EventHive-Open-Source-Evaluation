# Optimizations Considered and Implemented

## 1. Objective and baseline

The changes focused on correctness, maintainability, and predictable handling of events and reconciliation records rather than on unmeasured speed improvements.

Investigation identified these issues:

- Identified events needed replay protection.
- Missing or malformed event IDs needed explicit handling.
- Unsupported event types should not enter transition processing.
- Refund processing needed eligibility, amount, and outstanding-balance checks.
- Payment confirmation should not overwrite an existing non-`UNPAID` payment state.
- Internal and provider records use different amount-field names.
- Amount and status mismatches needed independent reporting.
- Missing or duplicate order IDs could make reconciliation ambiguous.

No formal performance baseline or profiling run was collected.

## 2. Options considered

### Option 1: Improve event idempotency and validation

**Expected benefit:** Prevent replay of identified events and reject unsupported event types or malformed identifiers before changing order state.

**Trade-off:** Events without IDs cannot be deduplicated by ID.

**Decision:** Implemented. Supported event types are allow-listed; empty, whitespace-only, and non-string non-None IDs are rejected. Identified event IDs are checked and recorded. Missing IDs are not added to the processed-ID list.

### Option 2: Require IDs for refund events

**Expected benefit:** Avoid applying a financial refund event that cannot be reliably protected against replay.

**Trade-off:** A refund event without an ID is ignored, even if its amount and order would otherwise be eligible.

**Decision:** Implemented. Non-refund events without IDs can still be processed independently; refund events without IDs are ignored.

### Option 3: Strengthen refund validation

**Expected benefit:** Prevent invalid refunds, refunds on ineligible orders, and refunds greater than the remaining due amount.

**Trade-off:** Additional validation conditions make the refund branch more explicit.

**Decision:** Implemented. Refunds require an eligible paid rejected/cancelled order, a positive outstanding balance, a positive integer amount no greater than that balance, and an event ID. Payment status changes to `REFUNDED` only when the full due amount is reached.

### Option 4: Make reconciliation field selection resilient

**Expected benefit:** Compare internal and provider amounts correctly despite their different field names and handle a preferred field whose value is `None`.

**Trade-off:** Supporting alternate field names adds fallback logic.

**Decision:** Implemented. Internal records prefer `total_paise` and fall back to `amount_paise`; provider records prefer `amount_paise` and fall back to `total_paise`.

### Option 5: Report reconciliation mismatches independently

**Expected benefit:** Avoid hiding a status mismatch when an amount mismatch also exists.

**Trade-off:** An order can appear in both mismatch categories.

**Decision:** Implemented. Amount and status are compared separately. An order is marked matched only if both agree.

### Option 6: Validate reconciliation identifiers

**Expected benefit:** Avoid silently overwriting duplicate records when constructing dictionaries and reject records that cannot be associated reliably.

**Trade-off:** Missing or duplicate order IDs now raise `ValueError`.

**Decision:** Implemented for both internal and provider inputs.

### Option 7: Introduce caching or a more complex event architecture

**Expected benefit:** Could help at larger scale or with more event types.

**Trade-off:** Adds memory, synchronization, or abstraction complexity without measured evidence that the current project needs it.

**Decision:** Not implemented. The existing function-based structure is sufficient for the current scope.

## 3. Changes implemented

### A. Event processing

- Validated event types against the supported event list.
- Rejected empty, whitespace-only, and non-string non-None event IDs.
- Checked identified events against the processed-ID list.
- Avoided storing missing IDs or treating multiple missing IDs as duplicates.
- Ignored refund events without IDs.
- Limited payment confirmation to orders currently marked `UNPAID`.

### B. Refund safety

- Checked order status and payment status eligibility.
- Required a positive integer refund amount.
- Checked the outstanding refund balance before accepting another refund.
- Kept payment status as `PAID` for partial refunds and changed it to `REFUNDED` only when the full due amount was reached.

### C. Reconciliation

- Added fallback handling for internal/provider amount field names when the preferred value is `None`.
- Reported amount and status mismatches independently.
- Added explicit missing/duplicate order-ID validation.

## 4. Regression coverage

Seven tests were added to `tests/test_contract.py`:

- `test_reconcile_internal_total_against_provider_amount`
- `test_events_without_event_id_are_processed_independently`
- `test_refund_without_event_id_is_ignored`
- `test_reconcile_reports_both_amount_and_status_mismatches`
- `test_reconcile_falls_back_when_preferred_amount_is_none`
- `test_reconcile_rejects_duplicate_internal_order_ids`
- `test_reconcile_rejects_duplicate_provider_order_ids`

The latest full test-suite run completed with **219 passed in 0.69s** using `python -m pytest -q`.

## 5. Trade-offs and measurements

The implemented changes prioritize correctness and predictable behaviour over performance claims.

- **Idempotency:** Identified events can be checked for replay. Events without IDs cannot be reliably deduplicated.
- **Refund safety:** Additional checks make financial state transitions more restrictive and explicit.
- **Reconciliation:** Alternative field names improve compatibility with the supplied records, while independent mismatch lists preserve both findings.
- **Identifier validation:** Rejecting missing or duplicate order IDs prevents ambiguous reconciliation rather than silently choosing one record.
- **Simplicity:** Caching and larger architectural changes were avoided because no profiling evidence justified them.

No speedup, memory reduction, or time-complexity improvement is claimed. The reported test duration is a test-run observation, not a benchmark.

## 6. Further improvements

With more time, possible next steps include:

1. Validate complete event and record schemas at ingestion.
2. Add a dedicated regression test for missing order IDs in both reconciliation inputs.
3. Replay the complete synthetic event dataset as a separate end-to-end verification.
4. Profile larger synthetic datasets before considering indexing or caching.
5. Add structured results or logs to distinguish ignored, invalid, duplicate, and successfully processed events.
