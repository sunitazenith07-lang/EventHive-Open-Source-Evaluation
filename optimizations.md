# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective

The objective was correctness, not speed. Refund processing accepted invalid amounts and could refund more than the amount due.

The original test suite produced 62 failures and 150 passes, and the refund tests listed in `challenges.md` were among the failing ones. No performance benchmark was conducted.

## 2. Options considered

**Option 1: One inline validation condition in the refund branch (chosen)**
- Expected benefit: Rejects invalid and excessive amounts with a small, readable change.
- Risk: The condition has several parts, so it could become hard to read if more rules are added.
- Decision: Accepted. It fixes the bug without restructuring `service.py`.

**Option 2: Move validation into a helper function**
- Expected benefit: Easier to reuse and test on its own.
- Risk: Adds a function and indirection for a single use.
- Decision: Rejected for now. It was not needed for this bug.

**Option 3: Raise an error for invalid amounts**
- Expected benefit: Makes bad events visible.
- Risk: Conflicts with the existing test name `test_invalid_refund_amounts_are_ignored`, which expects invalid amounts to be ignored.
- Decision: Rejected.

No alternative implementation was formally benchmarked.

## 3. Changes implemented

- Change: Added refund amount validation (integer, not boolean, positive, no greater than the remaining refund due) in the `refund_processed` branch.
  - Reason: Prevent invalid refunds and over-refunding.
  - Tests used: `test_invalid_refund_amounts_are_ignored`, `test_valid_partial_and_full_refunds`, `test_refunds_cannot_exceed_due`.
  - Measurement method and result: No performance measurement conducted.

## 4. Trade-offs

- Strict validation means malformed refund events are silently ignored rather than reported.
- The inline condition keeps the code simple but may justify a helper function if more refund rules are added.
- No refactoring was performed.

Correctness and maintainability were prioritised over unnecessary complexity.

## 5. Further improvements

With more time, I would:

1. Add a helper function for refund validation if more rules are added.
2. Add tests for several partial refunds that together equal the refund due.
3. Check whether an ignored invalid refund should still record its event ID as processed.

These would be validated with regression tests.

If you made no optimization change, state that honestly and compare at least two reasonable options. Correctness and maintainability take priority over unnecessary complexity.