# Test evidence

> AI-assisted implementation and notes. The student confirmed evaluator permission for AI assistance on 30 October 2026; Codex contributions are documented in AI_ASSISTANCE.md.

## Environment and commands

- Host: macOS, Python 3.14.7, pytest 9.2.0.
- Dependencies: `python -m pip install -r requirements-dev.txt` in an isolated venv.
- Untouched baseline: `python -m pytest -q --junitxml=<evidence-path>/baseline-tests.xml`.
  Actual result: **62 failed, 150 passed in 0.16s**.
- Original coverage: all **212 original cases** are included unchanged in the final run.
- Final suite: `python -m pytest -q --junitxml=<evidence-path>/final-tests.xml`.
  Actual result: **308 passed in 0.11s**, with no skips or expected failures.
- Offline demo: `python -m main`; exit 0, corrected match/status report.
- `git diff --check`: passed. Original tests, CI, models, fixtures, main, and data
  were checked unchanged against the baseline commit.

Durations above are observed single-run test times, not performance benchmarks.
Logs/XML and generated scenario outputs are in `evidence/`.

## Edge-case evidence

| Case / input | Expected behavior | Actual result | Evidence |
|---|---|---|---|
| Replay refund ID r1 after a 400-paise refund | Refunded remains 400; no duplicate history entry | Passed | `test_partial_duplicate_conflicting_payload_and_completion` |
| Same ID r1 with amount changed to 600 | ID takes precedence; no second effect | Passed | Same regression |
| Refund 601 when 600 remains | Reject entire amount; retain 400 refunded | Passed | Same regression |
| Refund remaining 600 | Due and refunded both 1000; payment REFUNDED | Passed | Same regression; walkthrough JSON |
| Refund True, 1.0, a string, negative, zero, None, list, dict | No money or payment-state change | Passed | `test_invalid_refund_preserves_money_and_is_idempotent` |
| Cancel paid order after dispatch | Remain OUT_FOR_DELIVERY with zero refund due | Passed | `test_cancel_after_dispatch_does_not_create_refund_obligation` |
| Cancel/reject unpaid order, then late payment | Establish due 1000; permit valid full refund | Passed | `test_late_payment_after_unpaid_terminal_event_establishes_due` |
| New payment ID after full refund | Stay REFUNDED | Passed | `test_new_payment_notification_cannot_reopen_fully_refunded_order` |
| Missing event ID/type, unknown type, wrong order ID | Exact copied no-op | Passed | `test_bad_envelope_or_unknown_order_is_an_exact_noop` |
| Premature refund, then payment/cancel, then replay | Original rejected event stays ineffective | Passed | `test_rejected_refund_is_consumed_and_cannot_become_effective_on_replay` |
| Missing/invalid snapshot fields or money bounds | Preserve original snapshot | Passed | `test_unsafe_snapshot_is_not_silently_repaired`; missing-field regression |
| Both amount and status differ | ID appears independently in both mismatch lists | Passed | `test_reconciliation_reports_both_mismatches_and_missing_sides_separately` |
| Internal total_paise vs provider amount_paise | Compare corresponding numeric values | Passed | `test_domain_totals_and_provider_amounts_reconcile_in_real_demo` |
| Repeated identical summary | Collapse and match once | Passed | `test_exact_duplicate_summaries_collapse_despite_metadata_difference` |
| Conflicting duplicate ID on either side | Raise ValueError in either row order | Passed | `test_conflicting_duplicate_summaries_raise_independent_of_order` |
| Missing/malformed summary data | Raise ValueError; no input mutation | Passed | `test_malformed_summary_never_becomes_false_match` |
| Empty reconciliation | Five empty lists | Passed | Original `test_empty_reconciliation` |
| Modify returned nested metadata/history | Original inputs stay unchanged | Passed | `test_returned_history_and_metadata_do_not_alias_inputs` |
| Larger synthetic dataset | Sorted discrepancies, safe event replay and bounded refunds | Passed | `test_full_dataset_reconciles_and_every_event_replay_is_safe` |

## Regression coverage

The two original files contain 212 collected cases. The new regression file adds
96 collected cases. They test multi-event outcomes, invalid inputs, complete
reconciliation outputs, row-order independence, input immutability, the real demo,
and dataset invariants. No original assertion or workflow was changed.

The dataset test covers all 150 internal orders and 163 provider records in
reconciliation. It routes event examples only to known order IDs; malformed or
unroutable examples are not silently used to create new orders. Its assertions
check bounds, no payment regression from REFUNDED, and immediate replay safety.
It does not claim that every supplied anomaly has an approved business resolution.

## Limits

No remaining failures were observed locally. Python 3.10/3.11, real payment APIs,
persistence, concurrency, and hidden tests were not run locally. Check the draft PR
for remote GitHub Actions status; these local results alone do not establish CI status.
The provided dataset contains some semantically inconsistent starting snapshots;
this patch does not claim to repair all historical inconsistencies.
