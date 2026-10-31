# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective

The objective was correctness, not speed. Refunds could be applied to orders that were not eligible.

The original test suite produced 62 failures and 150 passes, and `test_refund_eligibility_matrix` was among the failing tests. No performance benchmark was conducted.

## 2. Options considered

**Option 1: Check only the payment status**
- Expected benefit: Small change that stops refunds on unpaid orders.
- Risk: Does not stop refunds on paid orders in the wrong state.
- Decision: Rejected. The eligibility matrix still had a failing case (`FAILED` order with `PAID` payment status).

**Option 2: Check both payment status and order status in the existing condition (chosen)**
- Expected benefit: Covers both unpaid orders and paid orders in ineligible states with a small change.
- Risk: The allowed statuses are hard-coded, so they must stay consistent with the business rules.
- Decision: Accepted.

**Option 3: Move the eligibility rules into a helper function**
- Expected benefit: Easier to read and reuse.
- Risk: Adds a function and indirection for a single use.
- Decision: Rejected for now.

No alternative implementation was formally benchmarked.

## 3. Changes implemented

- Change: Added payment status (`PAID`) and order status (`REJECTED` or `CANCELLED`) checks to the refund condition.
  - Reason: Restrict refund processing to eligible paid orders.
  - Tests used: `test_refund_eligibility_matrix`.
  - Measurement method and result: No performance measurement conducted.

## 4. Trade-offs

- The condition is now long. It is readable, but adding more rules may justify a helper function.
- Hard-coded statuses are strict: if the business later allows refunds in other states, this condition must be updated.
- No refactoring was performed.

Correctness and maintainability were prioritised over unnecessary complexity.

## 5. Further improvements

With more time, I would:

1. Move the refund rules (amount, balance and eligibility) into one helper function if more rules are added.
2. Add tests for several partial refunds on an eligible order.
3. Check whether an ineligible refund should still record its event ID as processed.

These would be validated with regression tests.

If you made no optimization change, state that honestly and compare at least two reasonable options. Correctness and maintainability take priority over unnecessary complexity.