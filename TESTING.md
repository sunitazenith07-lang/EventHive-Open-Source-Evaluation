# TESTING.md — Required submission

## Test command and environment
- Python version: 3.14.5
- Command run: `python -m pytest -q`
- Actual test summary: Baseline before changes: **62 failed, 150 passed**. Final after changes: **216 passed**.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Repeat a `refund_processed` event with the same ID and partial amount | Apply the refund only once | Refunded amount remains 400 paise; event ID appears once | `test_duplicate_refund_event_is_idempotent` |
| 2 | Missing event ID/type or non-string event type | Ignore malformed event without changing state or history | Order remains placed and unpaid; event list is empty | `test_invalid_or_missing_event_fields_are_ignored` |
| 3 | Confirm payment after the order is cancelled | Mark paid and set full order total as refund due | Payment is `PAID`, due is 1000 paise | `test_payment_confirmed_after_cancellation_sets_refund_due` |
| 4 | Provider summary has a different amount and status | Report both mismatches; do not mark as matched | Order appears in both mismatch lists, not in `matched` | `test_reconciliation_reports_amount_and_status_mismatches_separately` |
| 5 | Request refund without an eligible paid cancelled/rejected order | Do not increase refunded amount | Refund amount remains zero | `test_refund_requires_eligible_order`; `test_refund_eligibility_matrix` |
| 6 | Request a refund greater than outstanding amount | Reject it without exceeding due balance | Refunded amount remains within the 5000-paise due balance | `test_refund_cannot_exceed_amount_due`; `test_refunds_cannot_exceed_due` |

## Regression tests added
- Duplicate partial-refund replay is idempotent.
- Missing and malformed event fields do not alter order state or record an event.
- Payment confirmed after cancellation establishes a refund due.
- Simultaneous amount and status mismatches are reported independently.

## Remaining failures or limitations
No test failures remain. Reconciliation resolves duplicate order IDs by keeping the last row in each input list.
