# TESTING.md — Test evidence

## Test command and environment

- Python version: 3.14.5
- Dependency setup: `python -m pip install -r requirements-dev.txt` — completed; pytest 8.4.2 installed.
- Test command: `python -m pytest -q`
- Actual latest result: **222 passed in 1.19s**, no warnings.
- The baseline before service changes was 62 failed, 150 passed, 1 warning. The initial test attempt before installing pytest did not run (`No module named pytest`).

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replay the same `payment_confirmed` event ID | Payment remains paid and event ID is recorded once | Pass | `test_duplicate_event_is_idempotent`; `test_payment_event_replay_idempotent` |
| 2 | Replay a 400-paise partial refund event | Refunded amount remains 400 paise, not 800 | Pass | `test_duplicate_refund_event_is_idempotent` |
| 3 | Refund an unpaid, non-cancelled order | No refund is added | Pass | `test_refund_requires_eligible_order`; `test_refund_eligibility_matrix` |
| 4 | Refund with zero, negative, fractional, boolean, missing, or over-due amount | Refund state does not change | Pass | `test_refund_must_be_positive`; `test_refund_cannot_exceed_amount_due`; `test_invalid_refund_amounts_are_ignored` |
| 5 | Request cancellation after dispatch | Keep `OUT_FOR_DELIVERY` | Pass | `test_cancel_after_dispatch_is_ignored`; transition matrix |
| 6 | Internal/provider rows have equal amount but different statuses | Report status mismatch and do not call it matched | Pass | `test_reconcile_reports_status_difference`; `test_reconciliation_status_mismatch_matrix` |
| 7 | Event is missing its ID/type or has a list as its type | Leave order unchanged | Pass | `test_missing_or_malformed_event_fields_do_not_change_order` |
| 8 | Reconcile empty inputs | Return all report lists empty | Pass | `test_empty_reconciliation` |
| 9 | Two partial refunds total exactly the due | Keep payment `PAID` after the first; set `REFUNDED` after the second | Pass | `test_two_partial_refunds_mark_refunded_only_at_full_due` |
| 10 | Second refund is one paise above remaining due | Do not apply the second refund | Pass | `test_refund_cannot_exceed_remaining_due_after_partial_refund` |
| 11 | Boolean `True` supplied as refund amount | Do not treat it as integer paise | Pass | `test_boolean_is_not_accepted_as_refund_amount` |
| 12 | Event has an empty event ID | Leave order unchanged and do not record the event | Pass | `test_empty_event_id_does_not_change_or_record_event` |
| 13 | Same record has amount and status mismatches | Report both mismatch categories and do not mark as matched | Pass | `test_reconciliation_reports_amount_and_status_mismatches_together` |
| 14 | Event payload is `None`, a list, or a string | Leave order unchanged | Pass | `test_non_dictionary_event_does_not_change_order` |
| 15 | Reconciliation input contains non-dictionary rows or rows with missing/null IDs | Ignore unkeyable rows and compare valid IDs | Pass | `test_reconciliation_skips_non_dictionary_and_missing_id_records` |
| 16 | `processed_event_ids` is malformed (`None`) | Return the order safely without applying an event | Pass | `test_invalid_processed_event_id_collection_does_not_raise` |

## Regression tests added

- `test_duplicate_refund_event_is_idempotent` guards against applying a repeated refund notification twice.
- `test_missing_or_malformed_event_fields_do_not_change_order` covers absent identifiers/types and an invalid unhashable event type.
- `tests/test_edge_cases.py` adds eight focused tests for partial-refund completion, remaining-due limits, invalid amounts/IDs, simultaneous mismatches, and malformed event/order-index inputs.
- It verifies that non-dictionary event payloads and malformed reconciliation rows do not raise or affect valid records.

## Remaining failures or limitations

- No test failures remain in the local Python 3.14.5 run.
- CI is configured for Python 3.11; that runtime was not available for a local run.
- The service remains an in-memory simulation without persistence or real payment-provider integration.
