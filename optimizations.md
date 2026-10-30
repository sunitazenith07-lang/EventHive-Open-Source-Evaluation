# optimizations.md - Required submission

## 1. Baseline and objective

The evidence pointed to correctness and predictable classification as the priority, not a measured performance bottleneck. Before fixes, the suite reported **62 failed, 150 passed**. There are no benchmark or profiler logs in the repository or from this work. The documented synthetic dataset has 150 internal orders, 163 provider records, and 219 event examples; those counts describe data size, not performance.

## 2. Options considered

- **Keep the simple list-backed event history:** this preserves the current order dictionary shape and keeps the implementation straightforward. A membership test over this list is linear in the number of stored event IDs, but the project has no measured workload showing that this is a bottleneck.
- **Use a set or persistent uniqueness constraint for event IDs:** a set can improve repeated membership checks for large event histories, while a database uniqueness constraint could enforce idempotency across processes. These options add serialization or persistence complexity and were not implemented or benchmarked.
- **Keep keyed reconciliation maps and sorted output:** maps make order lookup direct, and sorting makes reports deterministic as the tests require. Sorting has a cost but no measurement justifies removing it.
- **Retain deep-copy behavior:** copying protects caller-owned order records from mutation and is covered by tests. Removing or narrowing the copy could save work for large records, but could break that behavior; I did not measure the trade-off.

## 3. Changes implemented

- I implemented correctness safeguards, not performance optimizations: event replay checks, pre-mutation refund validation, and status-aware reconciliation.
- I added two regression tests; the existing suite plus new tests reports **214 passed, 1 warning in 0.56s**.
- No benchmark or profiler was run. The test duration is not a before/after performance measurement, and I make no speedup or memory-reduction claim.

## 4. Trade-offs

The event ID check uses the existing list representation, prioritizing compatibility and clarity over a more complex index. Refund validation adds conditions before mutation to protect monetary state. Reconciliation continues to build maps, union IDs, and sort results. By inspection, these data structures use memory proportional to the input rows and sorting grows with the number of unique IDs; this is asymptotic reasoning, not a measured bottleneck.

## 5. Further improvements

1. Benchmark replay checks using representative event histories before considering a set or persistent event-ID index; verify that any change preserves event serialization and duplicate semantics.
2. Profile reconciliation at larger synthetic sizes before changing its keyed lookup or deterministic sorting.
3. If the project expands beyond an offline exercise, assess durable transactional order/refund storage and provider integration. This would address process restarts and cross-process idempotency, but is outside the present in-memory implementation.

Correctness comes first. The current measured result is test correctness (214 passing tests), not runtime optimization.
