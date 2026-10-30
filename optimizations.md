# Optimizations and trade-offs

> AI-assisted reference. Evaluator approval for AI assistance has not been granted, as clarified by the student on 30 October 2026. Codex contributions are documented in AI_ASSISTANCE.md.

## Objective

Correctness and readable business rules were the priority. No performance benchmark
or measured speedup is claimed.

## Implemented choices

| Choice | Benefit | Trade-off / validation |
|---|---|---|
| Dictionary indexes for reconciliation | Lookup by ID rather than repeated scans | O(n+m) index space, then O(u log u) sorting for u unique IDs; dataset and permutation tests protect results. |
| One explicit lifecycle transition table | Makes permitted moves reviewable together | Adds constants, but avoids repeating eligibility branches; original state matrix passes unchanged. |
| Validate money before arithmetic | Prevents type errors, booleans, negative and excessive refunds | Adds boundary checks; invalid-amount and cumulative-refund regressions cover them. |
| Early duplicate return | Prevents repeated state and ledger updates | History membership remains O(h) for h recorded IDs, consistent with the supplied list shape. |
| Deep-copy returned state | Keeps history and nested metadata independent of caller-owned data | Copying costs time/memory proportional to snapshot size; aliasing regression verifies the contract. |

## Considered but not implemented

A separate set could accelerate history membership, but complicates the existing
JSON-serializable snapshot and synchronization. An in-memory cache would not make
idempotency durable. A database unique constraint and transactional ledger would be
appropriate for a concurrent service, but they are beyond this offline evaluation.
Skipping malformed reconciliation rows would keep reports running but could hide
financial discrepancies; explicit ValueError was chosen instead.

## Future work

If production scope were authorized, add durable event IDs and transactional updates,
structured rejection diagnostics, and a defined migration policy for inconsistent
snapshots. Benchmark representative histories before changing the data model.
These are proposals, not implemented or measured improvements.
