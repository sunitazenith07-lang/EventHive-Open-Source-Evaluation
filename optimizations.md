# optimizations.md - Required submission

## 1. Baseline and objective

The main objective was correctness and maintainability rather than raw speed. The baseline had 62 failing tests out of 212, including duplicate event application, unsafe refund arithmetic, and incorrect reconciliation classifications. The starter reconciliation already used dictionaries to index rows by order ID; its main gap was comparison logic and missing-field handling, not an observed performance bottleneck.

## 2. Options considered

- **Event ID tracking:** A separate set could make duplicate lookup average O(1), but would require another stored field or reconstruction. I retained the existing list-based `processed_event_ids` representation and a membership check to keep the order model compatible and simple. This lookup is O(k) in the number of events already processed for the order.
- **Copying order state:** A shallow dictionary copy would be cheaper, but it would share the nested `processed_event_ids` list with the caller. I retained `deepcopy` to protect input immutability.
- **Refund overrun handling:** Clipping an excessive request to the remaining due would preserve a partial amount, but it would silently change the requested event. Rejecting an invalid over-limit refund as a whole is easier to reason about and matches the acceptance tests.
- **Reconciliation:** A nested comparison of every internal row with every provider row would be O(n × m). Dictionary indexing keeps lookup work linear in the input sizes, followed by sorting the report IDs for stable output. The starter already had the dictionary structure, so I retained and completed it rather than adding a new abstraction.

## 3. Changes implemented

- Change: Added small input-validation helpers, duplicate-event protection, safe refund eligibility/bounds checks, and separate amount/status reconciliation checks.
- Reason: These changes address observed correctness failures while keeping the public function signatures and report keys unchanged.
- Tests used to protect correctness: the two supplied test modules plus 13 tests in `tests/test_regressions.py`; the final suite reported 225 passed.
- Measurement method and result: No before/after performance benchmark was run. The final pytest run completed in 0.19 seconds in this workspace, but that single run is not evidence of a speedup, so no performance improvement is claimed.

## 4. Trade-offs

The ID list is straightforward and preserves the existing order schema, but membership checks become slower as a single order accumulates many events. Deep copying protects caller data, especially nested fields, at the cost of copying the order on each event. Sorting report IDs adds O(k log k) work but gives stable output regardless of the input row order. Rejecting invalid refunds favors financial safety over accepting/clipping malformed provider requests.

## 5. Further improvements

With more time, I would define an explicit duplicate-order policy and add a duplicate-record bucket, persist processed event IDs so idempotency survives process restarts, and validate records against a documented schema at ingestion boundaries. I would benchmark reconciliation on larger synthetic inputs before changing data structures, and compare the current list ledger with a set-backed ledger while preserving serialized order history. Each improvement would need dedicated regression tests and repeatable before/after measurements.
