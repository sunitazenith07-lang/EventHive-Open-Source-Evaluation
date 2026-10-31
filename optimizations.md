# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective

This commit was about correctness, not speed. Reconciliation could report an order as matched even when the two statuses differed.

The original suite had 62 failures and 150 passes, and `test_reconciliation_status_mismatch_matrix` was one of the failing tests. No performance benchmark was run.

## 2. Options considered

**Option 1: Add an `elif` status comparison after the amount comparison (chosen)**
- Expected benefit: Fixes the misclassification with a small change and reuses the existing `status_mismatches` category.
- Risk: When both amount and status differ, only the amount mismatch is reported.
- Decision: Accepted.

**Option 2: Compare amount and status independently**
- Expected benefit: An order with both differences would show up in both lists, which is a fuller report.
- Risk: One order could appear in more than one category. That changes the report structure and may conflict with what the tests expect.
- Decision: Rejected for this bug and kept as a possible future improvement.

No alternative implementation was formally benchmarked.

## 3. Changes implemented

- Change: Added a status comparison to `reconcile_orders()` between the amount check and the `matched` case.
  - Reason: Orders with different statuses should go to `status_mismatches`, not `matched`.
  - Tests used: `test_reconciliation_status_mismatch_matrix`.
  - Measurement method and result: No performance measurement conducted.

## 4. Trade-offs

- The `if`/`elif`/`else` structure is simple and gives each order exactly one category, but it hides a status difference when the amount also differs.
- Reusing the existing report categories keeps the report format unchanged.
- No refactoring was done.

I chose correctness and maintainability over extra complexity.

## 5. Further improvements

With more time, I would:

1. Decide whether an order with both an amount and a status difference should appear in both categories, and write a test for it first.
2. Add tests for records with a missing amount or status field.
3. Benchmark reconciliation on larger synthetic datasets before making any performance-related change.

I would validate these with regression tests and, for performance, repeatable measurements against a defined baseline.

If you made no optimization change, state that honestly and compare at least two reasonable options. Correctness and maintainability take priority over unnecessary complexity.