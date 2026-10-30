# TESTING.md — Required submission

## Test command and environment
- Python version: 3.14.7
- Command run: `python -m pytest -q`
- Actual test summary: 226 passed, 0 failed (212 original tests + 14 added regression tests).

## Baseline
- Original test count: 212
- Original result: 150 passed, 62 failed
- Final result: 226 passed, 0 failed

## Demo command and output
- Command: `python -m main`
- Actual output:
  - `matched: ['ORD-101']`
  - `missing_from_provider: ['ORD-103']`
  - `missing_from_internal: ['ORD-104']`
  - `amount_mismatches: []`
  - `status_mismatches: ['ORD-102']`

## Edge-case evidence
| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replay `payment_confirmed` with the same event_id twice | Payment stays PAID and event ID appears once | PAID, processed_event_ids = [e1] | test_duplicate_event_is_idempotent |
| 2 | Refund 600 paise then 500 paise against 1000 paise due | First applies; second is ignored because only 400 paise remains | refunded_paise stays 600 | test_refunds_cannot_exceed_due |
| 3 | Refund amount True on a paid cancelled order | Ignored because bool is not an integer amount | refunded_paise = 0 | test_invalid_refund_amounts_are_ignored and regression test |
| 4 | Cancel request on an OUT_FOR_DELIVERY order | Status unchanged | OUT_FOR_DELIVERY | test_cancel_after_dispatch_is_ignored |
| 5 | Combined amount and status mismatch in reconciliation | Reported in both amount_mismatches and status_mismatches | Both lists contain the order ID | test_regression_reconciliation_combined_mismatch_both_categories |
| 6 | Internal total_paise compared with provider amount_paise | Matched when equal | matched = [A] | test_regression_reconciliation_maps_total_to_amount |

## Regression tests added
- tests/test_regressions.py contains 14 tests covering duplicate refund replay, ineligible refunds, bool amount rejection, over-limit refunds, partial accumulation to full refund, cancellation after dispatch, payment after rejection, status mismatch, combined mismatch, amount mapping, empty/malformed reconciliation, input immutability, unknown events, and conflicting replay.

## Remaining failures or limitations
- No test failures remain.
- Duplicate order IDs collapse to the first occurrence.
- Events without event_id are not deduplicated.
- Documentation files other than TESTING.md were completed in Phase 2.
