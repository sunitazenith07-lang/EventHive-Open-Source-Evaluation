# TESTING.md

## Test command and environment
- Python version: 3.14.7 (virtual environment `.venv`), macOS, pytest from `requirements-dev.txt`.
- Command run: `python -m pytest -q`
- Actual test summary:
  - Untouched starter: **62 failed, 150 passed in 0.25s**
  - After the fix, before adding my tests: **212 passed in 0.04s**
  - After adding `tests/test_regressions.py`: **246 passed**
- Demo: `python -m main` now prints `matched: ['ORD-101']`, `missing_from_provider: ['ORD-103']`, `missing_from_internal: ['ORD-104']`, `amount_mismatches: []`, `status_mismatches: ['ORD-102']`.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | The same `refund_processed` event (id `r1`, 400 paise) delivered twice | Counted once: `refunded_paise == 400`, ids `['r1']` | As expected | `test_replayed_refund_event_is_applied_only_once` |
| 2 | Event with a missing, empty, `None`, bool, list or float `event_id` | Ignored; order unchanged, nothing recorded | As expected (5 cases plus the missing-key case) | `test_event_without_usable_id_is_ignored`, `test_event_missing_id_key_is_ignored` |
| 3 | Refund amount `True`, `1000.0`, `"500"`, `None`, or no amount at all | Rejected; `refunded_paise == 0`, payment stays PAID | As expected | `test_non_integer_refund_amounts_are_rejected_even_if_numerically_valid`, `test_refund_event_without_amount_key_is_ignored` |
| 4 | Refund larger than the outstanding amount, and any refund after a full refund | Over-limit refund ignored entirely; order stays REFUNDED after the full refund | As expected | `test_refunds_cannot_exceed_due` (20 cases), `test_refund_after_full_refund_is_ignored` |
| 5 | Two partial refunds of 400 and 600 on a 1000 refund due | Still PAID after 400; REFUNDED only after the second | As expected | `test_two_partial_refunds_sum_to_full_and_complete_the_refund` |
| 6 | `payment_confirmed` with a new id after the order is fully REFUNDED | Stays REFUNDED, `refunded_paise` unchanged | As expected | `test_late_payment_confirmation_does_not_undo_refunded_status` |
| 7 | `payment_confirmed` after the order was cancelled | PAID, `refund_due_paise == total`, refund then allowed | As expected | `test_payment_after_cancellation_creates_refund_due_and_allows_refund` |
| 8 | Order that differs in both amount and status | Reported in both mismatch lists, not matched | As expected | `test_order_differing_in_amount_and_status_is_reported_in_both_lists` |
| 9 | Reconciliation with ids `7`, `10` and `"A"`; rows with no usable id; `None` lists | No crash; sorted as strings; bad rows skipped | As expected | `test_mixed_id_types_do_not_crash_and_sort_deterministically`, `test_rows_without_a_usable_order_id_are_skipped`, `test_none_inputs_behave_like_empty_lists` |
| 10 | Cancel after dispatch | Status stays OUT_FOR_DELIVERY | As expected | `test_cancel_after_dispatch_is_ignored` (original suite) |

## Regression tests added
`tests/test_regressions.py` holds 34 cases. Run against the untouched starter `service.py`, 29 of them fail and 5 pass; the 5 are guards for behaviour that must keep working (for example the string sort key in reconciliation).

| Defect fixed | Tests that guard it |
|---|---|
| Replays recorded and re-applied | replayed refund, unusable ids, non-dict events |
| Refund accepted without validation | non-integer amounts, refund after full refund, partial refunds adding up |
| Late payment reset REFUNDED to PAID | late payment confirmation |
| Money paid after cancellation could never be refunded | payment after cancellation |
| Status never compared in reconciliation | both-wrong order |
| Reconciliation crashes or hides rows | mixed ids, rows without ids, `None` inputs, `total_paise` fallback, zero amounts |

## Remaining failures or limitations
- No failing tests.
- A refund notification that arrives before the order is cancelled is ignored and its event id is spent, so it cannot be retried under the same id. `test_rejected_refund_id_is_still_recorded_so_it_cannot_be_retried` documents this on purpose.
- Rows without a usable `order_id` are skipped silently, and for duplicate ids in one list the last record wins.
- `apply_order_event` assumes `order` is a dict.