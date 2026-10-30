# Test evidence

## Environment and commands

Local verification used Python 3.12.14 and pytest 9.2.0 in an isolated virtual environment outside the checkout. From the repository root:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m main
python -m pytest -q --junitxml=../final-pytest.xml
git diff --check
```

- Untouched starter at `e006d24`: **62 failed, 150 passed in 0.15s**.
- Final suite: **301 passed in 0.07s**, with zero failures, errors or skips. This includes all 212 original cases and 89 new regression cases: 61 event cases and 28 reconciliation cases.
- The new reconciliation tests were also run against the starter: **24 failed, 4 passed**. They exposed schema, status, malformed-row and duplicate-record defects.
- The demo now prints `matched: ['ORD-101']`, `missing_from_provider: ['ORD-103']`, `missing_from_internal: ['ORD-104']`, `amount_mismatches: []`, and `status_mismatches: ['ORD-102']`.
- `git diff --check` passed. Original tests and both CI workflows are unchanged.

Activate your own environment before using the commands above. The XML path keeps generated evidence outside the checkout. Local Python 3.10/3.11 execution was unavailable; the existing GitHub workflow uses Python 3.11. Test timings are observations, not performance benchmarks.

## Edge-case evidence

All cases below passed in the final suite.

| Input or sequence | Expected result | Actual result | Regression evidence |
|---|---|---|---|
| Cancelled, paid order; refund 400 of 1000; replay same ID | Refund stays 400; one history entry | As expected | `test_replayed_partial_refund_does_not_pay_twice` |
| Reuse a payment event ID for cancellation | Original payment remains; no cancellation | As expected | `test_conflicting_payload_cannot_reuse_a_processed_id` |
| Dispatch while PLACED, then accept, then replay early dispatch | Early event remains refused; order stays ACCEPTED | As expected | `test_rejected_transition_is_recorded_and_cannot_apply_on_later_replay` |
| Missing event ID/type, unknown type, or malformed event container | Entire order and history unchanged | As expected | `test_missing_event_id_does_not_change_state_or_history`, `test_invalid_event_type_does_not_change_state_or_history`, `test_malformed_event_container_leaves_order_unchanged` |
| Event explicitly targets another order or invalid ID | No change | As expected | `test_wrong_or_invalid_target_cannot_change_order` |
| Unpaid cancellation or rejection followed by payment and refund | Late payment creates full due; refund completes | As expected | `test_late_payment_establishes_refund_due_for_unpaid_terminal_order` |
| Fresh payment event after completed refund | Payment stays REFUNDED | As expected | `test_fresh_payment_notification_cannot_revive_a_fully_refunded_order` |
| Refunds 300, 200, 501, 500 against due 1000 | Refuse 501; complete exactly at 1000 | As expected | `test_partial_refunds_complete_only_at_full_due_and_keep_due_unchanged` |
| Refund amount is bool, float, string, null, nonpositive, or too large | No refund amount change | As expected | Original `test_invalid_refund_amounts_are_ignored` and `test_refunds_cannot_exceed_due` |
| Cancellation after dispatch | OUT_FOR_DELIVERY remains unchanged | As expected | Original `test_cancel_after_dispatch_is_ignored` and transition matrix |
| Invalid order balances/history or missing required order fields | Leave input unchanged; no unsafe arithmetic | As expected | `test_invalid_order_accounting_or_history_is_not_modified`, `test_missing_required_order_field_is_not_fabricated` |
| Returned copy's nested metadata/history changed by caller | Original order and event remain unchanged | As expected | `test_returned_copy_does_not_alias_nested_input_or_event` |
| Internal total_paise versus provider amount_paise | Equal values match | As expected | `test_demo_reconciles_internal_totals_and_provider_amounts` |
| Same order differs in amount and status | ID appears in both mismatch lists, never matched | As expected | `test_amount_and_status_mismatches_are_independent` |
| Identifiable rows omit both comparison fields | Both mismatch lists contain the ID | As expected | `test_missing_comparison_fields_report_both_mismatches` |
| Missing or invalid row ID | Skip row; still report valid missing-side IDs | As expected | `test_unidentifiable_rows_are_ignored_without_hiding_valid_missing_orders` |
| Duplicate summaries disagree in amount or status | Corresponding mismatch, independent of input order | As expected | `test_conflicting_duplicates_report_the_affected_field` |
| Empty/None inputs | Empty report or valid missing-side IDs | As expected | `test_none_inputs_behave_as_empty_summaries` and original `test_empty_reconciliation` |

## Expanded dataset

`test_dataset_reconciliation_preserves_both_mismatch_categories` checks the supplied 150 internal orders and 163 provider summaries against independently calculated counts:

| Category | Actual count |
|---|---:|
| matched | 107 |
| missing_from_provider | 12 |
| missing_from_internal | 25 |
| amount_mismatches | 20 |
| status_mismatches | 12 |

`ORD-1078` appears in both mismatch categories. Reversing both input lists produces the same report; every output list is sorted.

An additional local stream probe processed all 212 addressed events from the 219 supplied examples. The caller skipped seven events with no order ID; there were no unknown targets. For every addressed event it checked source immutability, immediate replay equality, and `0 <= refunded_paise <= refund_due_paise <= total_paise`. All assertions passed. This probe was an additional manual check; the committed tests above are the reproducible regression suite.

## Remaining limitations

No failing local tests remain. This is an in-memory single-order API, without durable storage, concurrent updates, provider networking or a batch event router. Identifiers are nonempty strings and remain case-sensitive. The caller must resolve a target order before applying a batch event; the optional event order ID supports the existing single-order examples. Malformed unidentifiable reconciliation rows are skipped rather than returned in a new diagnostics category. Historical snapshots are validated for accounting safety, not repaired. See `AI_USAGE.md` for the assistance disclosure and evaluation-policy limitation.
