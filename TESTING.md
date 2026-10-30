# Testing evidence

This work was performed by Codex with AI assistance; see AI_USAGE.md.

## Environment and commands
- Python 3.12.14, Windows; isolated virtual environment.
- `python -m pip install -r requirements-dev.txt`: succeeded.
- Untouched baseline: `python -m pytest -q --tb=no`: **62 failed, 150 passed**.
- Final: `python -m pytest -q`: **235 passed**, no skipped tests.
- `python -m main`: succeeds; ORD-101 matched, ORD-102 status mismatch,
  ORD-103 missing from provider, ORD-104 missing from internal; no amount mismatches.
- Existing tests and workflows were preserved; 23 regression cases were added.

## Edge-case evidence
| Input | Expected | Actual | Test |
|---|---|---|---|
| Replay a 400-paise refund | Apply once | Passed | test_refund_sequence_and_replay |
| 400 then 600 against due 1000 | PAID after 400; REFUNDED after 1000 | Passed | test_refund_sequence_and_replay |
| New payment notification after full refund | Remain REFUNDED | Passed | test_refund_sequence_and_replay |
| Payment after unpaid cancellation/rejection | Establish full refund due | Passed | test_late_payment_creates_refund_due |
| Missing ID, malformed event, unknown order ID | Exact no-op | Passed | test_malformed_or_misrouted_event_is_noop |
| Same event ID with changed payload | Ignore changed event | Passed | test_duplicate_id_with_changed_payload_is_ignored |
| Negative/float/bool/excess refund | No monetary change | Passed | test_invalid_refund_amounts_are_ignored (existing) |
| Amount and status both differ | Report in both categories | Passed | test_reconciliation_reports_both_differences_and_normalizes_total |
| Missing comparison fields on both sides | Do not call matched | Passed | test_reconciliation_missing_fields_and_identical_duplicates |
| Conflicting duplicate order rows | Explicit ValueError in either ordering | Passed | test_conflicting_duplicate_records_rejected_in_either_order |
| Cancel after dispatch | Preserve delivery state | Passed | test_cancel_after_dispatch_is_ignored (existing) |

## Dataset coverage
The added dataset test routes all 219 supplied event examples across 150 orders,
checks input immutability, replay safety and refund bounds after each routed event,
and compares reconciliation against 163 provider records in both input orders.
It checks invariants rather than asserting every business outcome in the dataset.

## Limitations
No local failures remain. GitHub CI has not been run for this change.
Only Python 3.12 was tested locally; Python 3.10/3.11 compatibility is not independently verified.
No persistence, concurrency protection, provider API or durable global event registry is implemented.
Unidentifiable reconciliation rows are skipped; conflicting duplicates raise ValueError.
