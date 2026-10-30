# TESTING.md — Required submission

## Test command and environment

- Baseline environment: Python 3.14.7 on Windows (the initial run shared from PowerShell).
- Baseline command: `py -m pytest -q`
- Baseline result before changes: **150 passed, 62 failed (212 total)** in 1.56 seconds.
- Final verification environment: Python 3.13.5 in the project build workspace.
- Final command: `python -m pytest -q`
- Final result after the implementation and 13 additional regression tests: **225 passed, 0 failed** in 0.16 seconds.
- Additional checks: `python -m compileall -q .` completed successfully; `python -m main` completed and printed the reconciliation report shown below.
- Full synthetic-dataset reconciliation check: processed 150 internal orders and 163 provider records; report counts were 107 matched, 12 missing from provider, 25 missing from internal, 20 amount mismatches, and 12 status mismatches. This was an exploratory run, not a separately asserted pytest test.

Final demo output:

```text
matched: ['ORD-101']
missing_from_provider: ['ORD-103']
missing_from_internal: ['ORD-104']
amount_mismatches: []
status_mismatches: ['ORD-102']
```

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replay a `refund_processed` event with the same event ID after a 600-paise refund | The second delivery must not apply the refund again | `refunded_paise` remained 600 and the event ID appeared once | `test_duplicate_refund_event_does_not_apply_twice` |
| 2 | Refund amount is `True`, `0.5`, a numeric string, `None`, a list, or a dictionary | Reject the value; paise must be a positive integer, and `bool` is not accepted as an integer amount | Refund total remained 0 and payment stayed `PAID` | `test_refund_requires_integer_paise_and_rejects_bool` |
| 3 | Refund due is 1,000 paise; first refund is 700 and second request is 301 | Reject the second request because it exceeds the 300-paise outstanding balance | Refund total remained 700 and payment stayed `PAID` | `test_cumulative_refund_cannot_exceed_due` |
| 4 | Refund due is 1,000 paise; process 999 and then 1 | Keep payment `PAID` while partial; mark `REFUNDED` only when the full due is reached | First result was 999 / `PAID`; second was 1,000 / `REFUNDED` | `test_full_refund_only_marks_refunded_when_due_is_reached` |
| 5 | Same order ID has both an amount difference and a status difference | Report both discrepancies separately and do not classify the order as matched | Order `A` appeared in both mismatch lists and not in `matched` | `test_reconciliation_reports_both_amount_and_status_mismatches` |
| 6 | Internal order has `total_paise=45900`; provider row has `amount_paise=45900` | Compare the internal order total with the provider amount | Order `A` was matched with no amount mismatch | `test_reconciliation_maps_internal_total_to_provider_amount` |
| 7 | Event has no ID, an unknown type, a non-string type, or an ID for a different order | Ignore it without changing the order | The order remained unchanged | `test_event_without_id_or_unknown_type_is_ignored`; `test_malformed_event_type_and_wrong_order_id_are_ignored` |

## Regression tests added

Added `tests/test_regressions.py` with 13 tests covering duplicate refund replay, conflicting payload reuse of an event ID, missing IDs and unknown types, integer-only refund validation, cumulative refund bounds, exact full-refund completion, simultaneous amount/status mismatches, malformed reconciliation records, deterministic mixed-type IDs, late payment confirmation after cancellation, malformed event types and wrong-order events, invalid reconciliation amounts, and the `total_paise`/`amount_paise` field mapping.

The two supplied test files were retained unchanged. No tests or GitHub Actions workflows were removed, skipped, weakened, or edited to hide failures.

## Remaining failures or limitations

- No test failures remained in the final local run (225 passed).
- Reconciliation assumes one authoritative row per order ID on each side. If duplicate rows occur, the last row in that input is used; there is no separate duplicate-record report bucket.
- Rows without a usable order ID are ignored because the report schema has no invalid-record category.
- Events without a usable event ID and unknown event types are ignored. The service is an in-memory function and does not persist event IDs across process restarts.
- The final verification was run under Python 3.13.5 in this workspace. The initial Windows baseline was run under Python 3.14.7; rerun `py -m pytest -q` locally before submission if you need a post-change result for that exact environment.
