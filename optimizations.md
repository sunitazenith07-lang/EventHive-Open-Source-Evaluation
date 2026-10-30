# optimizations.md - OrderOps trade-offs

AI assistance was used for this work; verify that this is permitted before submitting it for evaluation. No speedup was measured.

## 1. Baseline and objective
The observed gap was correctness, not runtime performance: the baseline had 62 failing tests, including refund bounds and reconciliation status checks.

## 2. Options considered
- A handler registry could organize event dispatch but adds indirection for seven event types; the current explicit branches remain easier to compare with the transition matrix.
- A specialized reconciliation structure was not justified. The existing dictionaries already provide direct order-ID lookup.

## 3. Changes implemented
- Added event replay checks and refund eligibility/bounds validation.
- Classified amount and status differences independently.
- Added regressions for replay, malformed events, reconciliation, and the end-to-end refund path.
- Final correctness evidence: 219 tests passed. No performance benchmark was run.

## 4. Trade-offs
Validation adds conditions to `apply_order_event`, but avoids introducing helper abstractions or optional features. No performance claim is made.

## 5. Further improvements
Define behavior for duplicate order-summary IDs and test malformed summary rows. Benchmark reconciliation on representative data before attempting performance changes.