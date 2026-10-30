# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The starter refund_processed path applied every refund amount without checking eligibility, amount type, sign, or outstanding due. Replay handling was also missing, so the same refund event could be applied more than once.

## 2. Evidence
- test_refund_requires_eligible_order expected no refund on a placed unpaid order, but the starter added 500 paise.
- test_refund_must_be_positive expected 0 refunded for amounts 0 and -10, but the starter added -10.
- test_refund_cannot_exceed_amount_due expected 0 refunded for 1200 paise against a 1000 paise due, but the starter added 1200.
- test_duplicate_event_is_idempotent expected processed_event_ids to contain e1 once, but replay appended e1 again.
- test_reconcile_reports_status_difference expected a status mismatch, but the starter reported the record as matched.

## 3. What I tried
I ran the baseline suite and read the failing assertions. I then traced apply_order_event for each failing case to identify missing guards. For reconciliation, I compared the demo output against the fixture data and found that status was only checked in the else branch after amounts matched.

## 4. Resolution
I added an early idempotency check using event_id. I added eligibility, integer type, positivity, and outstanding-due checks to refund_processed. I made reconciliation compare internal total_paise as a fallback amount and evaluate status independently.

## 5. Proof and regression prevention
The 14 tests in tests/test_regressions.py cover duplicate refunds, invalid amounts, over-limit refunds, partial accumulation, cancellation after dispatch, payment after rejection, status and combined mismatches, amount mapping, and input immutability. The full suite passes: 226 passed, 0 failed.

## 6. Unresolved challenge or next step
Duplicate order IDs are collapsed to their first occurrence because the report schema has no duplicate category. Anonymous events are not deduplicated. These are documented limitations rather than hidden failures.
