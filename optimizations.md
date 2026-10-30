# Optimizations and trade-offs — OrderOps

## Objective
The primary goal was correctness and maintainability, not throughput. The initial observed suite reported 62 failures out of 212 tests; the corrected branch produced 212 passes.

## Design options
| Area | Choice | Alternative | Trade-off |
|---|---|---|---|
| Idempotency | Check processed IDs before applying the event | Reapply and repair state afterwards | Simple correctness; membership in a list grows with event history |
| Input state | Deep-copy order before modification | Mutate in place | Extra memory/copy cost, but protects caller state |
| Refund validation | Reject invalid type, eligibility, and excess amount | Coerce or clamp values | Strict validation avoids unintended financial movement |
| Reconciliation | Dictionary lookup by order ID | Nested scan through both lists | Simpler direct ID comparison and typically better scaling |
| Report order | Sort union of IDs by string form | Preserve arbitrary input order | Stable deterministic reports |

## Changes made
The corrected service validates events and refunds before state changes and classifies reconciliation differences independently. This prevents repeated or invalid financial updates while retaining deterministic output.

## Measurements
- Observed pytest results: **212 passed, 1 warning** in **0.84s** and **0.94s** on the fix branch.
- These are test-suite runtimes, not performance benchmarks. No speedup has been measured or claimed.

## Further improvements
- Consider a set for processed event IDs when optimizing very large event streams, while retaining compatibility with the current list-based data contract.
- Add stress tests for duplicate order IDs and malformed provider records if their required behavior is specified.
- Add structured logging for event outcomes, rejected refunds, and reconciliation exceptions in a production implementation.

## Limitations
No production-load profiling, security audit, or hidden-test validation was performed. The one pytest warning comes from an installed dependency rather than application logic.
