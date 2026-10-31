# optimizations.md - Required submission

## 1. Baseline and objective

- What needed improvement: The main improvement needed was correctness and maintainability of the refund-processing logic.
- Evidence: The initial test run showed 23 failures related to partial refunds and multiple refund events. The payment status was changing too early after a partial refund.

## 2. Options considered

**Option 1: Keep PARTIALLY_REFUNDED as the payment status**

- Expected benefit: It would explicitly represent a partial refund state.
- Risk: The existing refund eligibility condition expected the status to remain `PAID`, so subsequent valid refund events could be rejected.
- Decision: Rejected because it did not match the visible test contract.

**Option 2: Keep PAID until the full refund is completed**

- Expected benefit: Allows multiple valid refund events to accumulate while keeping the payment status consistent with the expected behaviour.
- Risk: The payment status alone does not explicitly distinguish a partial refund from no refund.
- Decision: Implemented because it matched the required behaviour and passed the visible tests.

## 3. Changes implemented

- Change: Removed the assignment of `PARTIALLY_REFUNDED` after a partial refund.
- Reason: Keep the payment status as `PAID` until the full refund amount has been processed. Set it to `REFUNDED` only when the full amount is reached.
- Tests used to protect correctness: The visible pytest suite, including partial refund, multiple refund event, and refund limit tests.
- Measurement method and result: No performance benchmark was conducted. The final visible test suite completed in 0.26 seconds with 212 tests passing. This is a test execution time, not a measured optimization speedup.

## 4. Trade-offs

Keeping the status as `PAID` during a partial refund is simpler and matches the visible test contract. However, it means the payment status alone does not communicate that a partial refund has already happened. The `refunded_paise` and `refund_due_paise` fields provide that information.

Correctness and compatibility with the expected behaviour were prioritised over adding a new payment status.

## 5. Further improvements

- Add more tests for duplicate refund event IDs and invalid refund amounts.
- Review order event handling for unusual event sequences.
- Consider adding clearer validation and documentation for refund state transitions.
- Run performance benchmarks on larger synthetic datasets before making performance-related changes.

These improvements should be validated with additional automated tests and measured benchmarks where relevant.