# Challenges Faced

## 1. Challenge or confusing behaviour

The main investigation involved reconciliation reporting amount mismatches for records whose amounts appeared to match. Other issues involved event replay protection, missing or malformed event IDs, refund eligibility and limits, and ambiguous reconciliation records.

## 2. Evidence

The initial demo output recorded during investigation was:

```text
matched: []
missing_from_provider: ['ORD-103']
missing_from_internal: ['ORD-104']
amount_mismatches: ['ORD-101', 'ORD-102']
status_mismatches: []
```

Inspection of the fixtures showed that internal records used `total_paise`, whereas provider records used `amount_paise`.

I also found that treating `None` as a normal event ID could cause unrelated events without IDs to be treated as duplicates. Refund events without IDs needed separate handling because they affect financial state and cannot be reliably protected against replay without an identifier.

## 3. What I investigated

- Ran `python -m main` and inspected the reconciliation output.
- Inspected `fixtures.py`, `models.py`, and `service.py` to understand how records and events were represented.
- Compared the amount fields used by internal and provider records.
- Ran targeted pytest selections while investigating idempotency and refund validation.
- Added regression tests for amount-field mapping, independent events without IDs, refunds without IDs, independent mismatch reporting, fallback fields, and duplicate order IDs.
- Ran the complete test suite after the changes.

## 4. Resolution

### Event processing

The event processor now accepts only the seven supported event types. Empty, whitespace-only, and non-string non-None event IDs are rejected. Identified events are checked against `processed_event_ids` to prevent replay.

Non-refund events without IDs can be processed independently; missing IDs are not recorded as processed IDs. Refund events without IDs are ignored because they cannot be reliably deduplicated.

Payment confirmation only changes payment status when it is currently `UNPAID`. Refund processing also checks that a positive refundable balance remains before accepting another refund.

### Refund validation

Refunds are restricted to paid orders in `REJECTED` or `CANCELLED` states. The amount must be a positive integer and cannot exceed the outstanding refund due. A partial refund leaves payment status as `PAID`; status becomes `REFUNDED` only when the full due amount is processed.

### Reconciliation

The reconciliation function now reads `total_paise` from internal records and `amount_paise` from provider records, falling back to the alternate field when the preferred value is `None`.

Amount and status mismatches are reported independently. Records are marked matched only when both agree. Missing/empty and duplicate order IDs raise `ValueError` before lookup dictionaries are constructed.

## 5. Regression prevention and proof

Seven regression tests were added:

- `test_reconcile_internal_total_against_provider_amount`
- `test_events_without_event_id_are_processed_independently`
- `test_refund_without_event_id_is_ignored`
- `test_reconcile_reports_both_amount_and_status_mismatches`
- `test_reconcile_falls_back_when_preferred_amount_is_none`
- `test_reconcile_rejects_duplicate_internal_order_ids`
- `test_reconcile_rejects_duplicate_provider_order_ids`

The latest full test-suite run completed with **219 passed in 0.69s**. The recorded demo output after the reconciliation field correction showed `ORD-101` as matched and `ORD-102` as a status mismatch.

## 6. Unresolved challenges and limitations

Events without IDs cannot be reliably deduplicated because there is no unique identifier to track replay. The implementation allows independent non-refund events without IDs but ignores refund events without them.

The complete synthetic event dataset was not replayed end-to-end as a separate test. No formal performance benchmark was conducted, and no performance improvement is claimed.
