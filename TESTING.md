# TESTING.md — Test evidence

## Test command and environment

- Python version: 3.14.5
- Dependency setup: `python -m pip install -r requirements-dev.txt` — completed; pytest 9.2.0 installed.
- Test command: `python -m pytest -q`
- Actual result after changes: **214 passed, 1 warning in 0.56s**.
- Warning: `PytestRemovedIn10Warning` from the installed `anyio` pytest plugin (`CallSpec2` renamed to `CallSpec`).
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

## Regression tests added

- `test_duplicate_refund_event_is_idempotent` guards against applying a repeated refund notification twice.
- `test_missing_or_malformed_event_fields_do_not_change_order` covers absent identifiers/types and an invalid unhashable event type.

## Remaining failures or limitations

- No test failures remain in the local Python 3.14.5 run.
- CI is configured for Python 3.11; that runtime was not available for a local run.
- The installed `anyio` pytest plugin emits one deprecation warning.
- The service remains an in-memory simulation without persistence or real payment-provider integration.
