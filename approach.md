# Approach and implementation record

Authorship: Codex, AI-assisted at the user's request. This is an engineering record,
not a claim that the student independently performed the work.

## Baseline and data flow
Read repository instructions, source, tests, data schema/catalog and CI configuration.
Created an isolated Python 3.12.14 environment and installed requirements-dev.txt.
Baseline: 62 failed, 150 passed. The offline demo incorrectly reported ORD-101 and
ORD-102 as amount mismatches and omitted the ORD-102 status mismatch.
models.new_order constructs dictionaries; apply_order_event returns a deep copy;
main uses fixtures directly as input to reconcile_orders.

## Root causes and fixes
- Event IDs were appended without a replay guard. Validate IDs and reject replays before mutation.
- Refund processing added arbitrary values without checking type, eligibility or outstanding due.
  Validate exact integer type, positive amount, paid eligible state and remaining balance.
- Payment confirmation always set PAID, reopening completed refunds. Only transition UNPAID to PAID;
  establish refund due for late payments on cancelled/rejected orders.
- Reconciliation compared amount only, and fixtures used total_paise rather than amount_paise.
  Normalize the two schemas and compare amount and status independently.
- Missing IDs and malformed payloads could pollute history or raise errors. Guard before updating.

## Decisions
Keep the pure copy-returning API and existing dictionary shapes. Use an explicit transition map
rather than unrelated mutable handlers. Reject excess refunds rather than clipping them.
Keep original refund obligation separate from cumulative processed amount.
Identical reconciliation duplicates collapse; conflicting duplicates raise ValueError rather
than selecting a winner based on input ordering. Unidentifiable records are skipped;
missing comparison fields are mismatches. These policies are documented, not hidden.

## Verification
Added 23 regression cases in tests/test_regressions.py, including dataset invariants.
Final suite: 235 passed. Demo now correctly reports ORD-101 matched, ORD-102 status mismatch,
ORD-103 missing from provider and ORD-104 missing from internal. See TESTING.md for commands,
edge cases and limitations. Existing tests and workflows were not altered.
