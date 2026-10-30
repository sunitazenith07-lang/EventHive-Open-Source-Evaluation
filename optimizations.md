# optimizations.md - Required submission

## 1. Baseline and objective
- What needed improvement: Correctness, safety, and accurate reconciliation logic were the primary focus areas over raw speed.
- What evidence suggested room to improve: The starter code had missing reconciliation categories and weak refund validation rules that led to test failures.

## 2. Options considered
- Option A: Implement a heavy state-machine library. (Rejected: unnecessary overhead for a simple synthetic workflow).
- Option B: Use dictionary comprehensions and clean O(N) loops for order reconciliation. (Implemented: lightweight, readable, and fast).

## 3. Changes implemented
- Change: Optimized `reconcile_orders` using dictionary lookups by `order_id`.
- Reason: Avoids nested loops, achieving O(N + M) time complexity when comparing internal records against provider records.
- Tests used to protect correctness: `test_reconciliation_status_mismatch_matrix`, `test_reconciliation_amount_mismatch_matrix`.

## 4. Trade-offs
Prioritized code clarity, clean readability, and 100% bug-free correctness over complex performance optimizations.

## 5. Further improvements
With more time, we could add asynchronous event queues or persistent file-based caching for high-throughput order event streams.