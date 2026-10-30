# Optimizations and trade-offs

## Implemented
Reconciliation builds dictionaries keyed by order_id once, then checks the union of keys in sorted order. This keeps comparison linear in the number of records aside from sorting and produces deterministic output. Status and amount checks are independent, so a record can report both discrepancies; it is marked matched only if neither differs.

Event handling uses a deep copy to preserve the existing non-mutating contract. Explicit guards favor readable state safety over compact transition tables. Processed IDs are a list to preserve the existing order schema and expected serialization; membership is linear, which is acceptable for this small synthetic service.

## Evidence and future work
The measurable validation was the suite changing from 62 failed/150 passed at baseline to 212 passed after implementation. No timing or large-dataset benchmark was run, so no performance gain is claimed. For a persistent high-volume service, I would consider a set or durable idempotency store, concurrency-safe updates, and validated schemas at the API boundary; those add dependencies and operational complexity and are not needed for this in-memory demo.
