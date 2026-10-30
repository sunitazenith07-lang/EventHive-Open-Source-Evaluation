# optimizations.md - Required submission

## 1. Baseline and objective
- What needed improvement (correctness, clarity, time complexity, memory, repeated work, maintainability)? Correctness and input validation: duplicate events and invalid refunds could corrupt order state, and reconciliation missed status mismatches.
- What evidence suggested there was room to improve? The baseline suite had **62 failures**, including refund and reconciliation assertions. No performance bottleneck was measured.

## 2. Options considered
- Deterministic reconciliation sorting costs `O(n log n)` but makes report order predictable. I kept it because deterministic output is part of the requirements; no large-input benchmark justified changing it.
- Refund validation could be repeated inline or shared through a helper. I used a small integer-paise helper so the bool exclusion is consistent for totals, due amounts, and event amounts.
- Adding result keys for malformed reconciliation rows would alter the report shape. I did not add keys; missing amount and status values are reported in their respective mismatch lists.

## 3. Changes implemented
- Change: Added integer-paise validation that excludes booleans and limited refunds to the outstanding amount.
- Reason: Prevent invalid values and cumulative refunds above the amount due.
- Tests used to protect correctness: Refund eligibility/amount matrices and the added duplicate-refund regression test.
- Measurement method and result (only if measured): No performance measurement was run; no speedup is claimed.

## 4. Trade-offs
Explicit checks add lines to the event handler but make the acceptance rules clear and prevent invalid monetary values. Sorting reconciliation keys favors deterministic output over linear-time ordering.

## 5. Further improvements
Define and test a duplicate-order-ID policy, then report duplicates explicitly or aggregate them. Benchmark reconciliation with representative large inputs before changing its sorting or memory behavior.
