# Project notes

## Requirements completed
1. Processed all 7 core event types: `payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, and `refund_processed`.
2. Enforced rigid state machine invariants: cancellations after dispatch do not modify state.
3. Implemented robust idempotency leveraging `event_id` deduplication.
4. Guaranteed integer-paise calculations: validated strictly positive integers, preventing boolean or float coercion, and bounded refunds against outstanding due.
5. Tracked `refund_due_paise` and `refunded_paise` independently: maintained `PAID` status across partial refunds, switching to `REFUNDED` only upon full settlement.
6. Reconciled internal and provider summaries deterministically with independent reporting of missing, amount mismatch, and status mismatch records.
7. Handled edge cases: malformed records, empty inputs, unknown IDs, and out-of-order late events.

## Files changed and why
- `service.py`: Fixed idempotency bug, corrected state transition validation, added strict integer and bounds checking for refunds, and separated reconciliation mismatch categories.
- `tests/test_regression_edge_cases.py`: Added 10 regression and edge case tests verifying boundary conditions and synthetic dataset anomalies.
- `approach.md`, `challenges.md`, `optimizations.md`: Completed compulsory problem-solving documentation.
- `TESTING.md`: Documented test environment, edge-case table, and verification results.
- `ORDER_FLOW_NOTES.md`: Provided full example event trace, edge case analysis, and operational assumptions.
- `ARCHITECTURE_TEMPLATE.md`: Documented system architecture, state transitions, and file map.
- `AI_USAGE_TEMPLATE.md`: Filled integrity template.

## Tests run
- `python -m pytest -q` -> 222 passed in 0.50s (baseline: 62 failed, 150 passed).
- `python -m main` -> Verified demo reconciliation output.

## Assumptions
- Order currency is denominated in integer paise (no fractional paise).
- Reconciliation evaluates matching records using `order_id` as primary key.
- A cancelled or rejected order that was paid is entitled to a 100% refund of `total_paise`.

## Known limitations
- Idempotency event tracking is stored in-memory per order dictionary. In a production microservice architecture, this should be backed by an external distributed store with a retention TTL.
