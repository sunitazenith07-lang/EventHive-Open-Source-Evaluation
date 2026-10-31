# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective

The objective was correctness, not speed. Reconciliation could report orders as matched when their statuses differed.

The original test suite produced 62 failures and 150 passes, and `test_reconciliation_status_mismatch_matrix` was among the failing tests. No performance benchmark was conducted.

## 2. Options considered

**Option 1: Add an `elif` status comparison after the amount comparison (chosen)**
- Expected benefit: Fixes the misclassification with a small change and uses the existing `status_mismatches` category.
- Risk: If both amount and status differ, only the amount mismatch is reported.
- Decision: Accepted.

**Option 2: Check amount and status independently**
- Expected benefit: An order with both differences would appear in both lists, giving a fuller report.
- Risk: One order could appear in more than one category, which changes the report structure and may conflict with what the tests expect.
- Decision: Rejected for this bug; left as a possible future improvement.

No alternative implementation was formally benchmarked.

## 3. Changes implemented

- Change: Added a status comparison to `reconcile_orders()` between the amount check and the `matched` case.
  - Reason: Report orders with different statuses under `status_mismatches` instead of `matched`.
  - Tests used: `test_reconciliation_status_mismatch_matrix`.
  - Measurement method and result: No performance measurement conducted.

## 4. Trade-offs

- The `if`/`elif`/`else` structure is simple and puts each order in exactly one category, but hides a status difference when the amount also differs.
- Reusing the existing report categories avoids changing the report format.
- No refactoring was performed.

Correctness and maintainability were prioritised over unnecessary complexity.

## 5. Further improvements

With more time, I would:

1. Decide whether orders with both an amount and a status difference should be reported in both categories, and add a test for that case first.
2. Add tests for records with missing amount or status fields.
3. Benchmark reconciliation with larger synthetic datasets before making any performance-related change.

These would be validated with regression tests and, for performance, repeatable measurements against a defined baseline.

If you made no optimization change, state that honestly and compare at least two reasonable options. Correctness and maintainability take priority over unnecessary complexity.