# Optimizations and trade-offs

AI-assisted engineering record by Codex. No performance speedup was measured or claimed.

## Objective and implemented changes
Correctness and clarity were the goals: replay protection, bounded refund arithmetic and independent
reconciliation categories. A transition map makes allowed source/target states explicit. Early validation
prevents malformed data from reaching monetary updates. Reconciliation retains dictionary indexing
and sorted output, with O(n + m + k log k) time for n internal rows, m provider rows and k distinct IDs.
Final correctness evidence: 235 passing tests, including 23 added regression cases.

## Options considered
- A set for processed IDs could improve repeated membership checks, but serialized history is a list.
  Keeping it avoids schema changes and preserves readable chronological history. Membership is O(h).
- In-place mutation would avoid deepcopy cost, but would violate the API's immutability guarantee.
  Retained deep copies and added sequence tests checking that inputs remain unchanged.
- Sorting input records is unnecessary: index by ID, then sort unique output keys once.
- Automatically clipping excess refunds would conceal invalid provider data; reject the amount instead.

## Future improvements
For a persistent concurrent service, add transactional uniqueness on (order_id, event_id) and atomic
refund balance updates. Benchmark long histories before replacing the current list representation.
Add a separate validation report if callers need detailed diagnostics for skipped malformed rows.
No stretch item or speculative performance infrastructure was implemented.
