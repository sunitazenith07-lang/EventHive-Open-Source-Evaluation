# Project notes

## Requirements completed
- [x] Process all 7 events: `payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, and `refund_processed`.
- [x] Enforce valid state transitions (including rejection of cancellation after dispatch).
- [x] Enforce event idempotency using `event_id` deduplication without corrupting order state.
- [x] Validate refund amounts in positive integer paise, reject non-integers and booleans, enforce upper bound against remaining due, and require eligibility (`REJECTED`/`CANCELLED` and `PAID`).
- [x] Support partial refunds while keeping `payment_status="PAID"` until the entire balance is refunded.
- [x] Reconcile internal and provider summaries deterministically, reporting missing orders, amount mismatches, and status mismatches separately.
- [x] Added 9 regression tests and passed all 221 tests (100%).

## Files changed and why
- `service.py`: Fixed idempotency check, refund eligibility and type validation, late payment handling, and reconciliation mismatch logic.
- `tests/test_regression.py`: Added 9 regression tests to prevent recurrence of fixed bugs.
- `approach.md`, `challenges.md`, `optimizations.md`: Completed the three mandatory 5-mark documents detailing empirical evidence, technical struggles, and optimizations.
- `TESTING.md`: Filled with exact Python version, command runs, 5 edge-case tables, and test descriptions.
- `ORDER_FLOW_NOTES.md`: Documented the 5-step order event lifecycle and edge cases.
- `ARCHITECTURE.md`: Documented the system architecture and state transition model.

## Tests run
- `python -m pytest -q`: 221 passed in 0.59s.
- `python -m main`: Verified offline reconciliation output.

## Assumptions
- Monetary values are in integer paise.
- Event timestamps or order of arrival follows standard lifecycle in happy path, with graceful handling of out-of-order late payment.

## Known limitations
- The service operates in-memory; high-throughput distributed deployments would require an external event queue (e.g. Kafka) and relational transactional persistence.
