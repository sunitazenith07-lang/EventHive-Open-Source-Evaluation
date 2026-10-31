# Project Notes — OrderOps

## Requirements Completed
1. **Event Processing:** Successfully processed all 7 order lifecycle events (`payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, `refund_processed`).
2. **Transition Enforcement:** Protected post-dispatch orders (`OUT_FOR_DELIVERY`, `DELIVERED`) against cancellation; enforced valid state flow from `PLACED`.
3. **Idempotency by `event_id`:** Guarded state mutation and `processed_event_ids` tracking so replayed events produce zero state changes and zero duplicate entries.
4. **Integer Paise & Refund Validation:** Enforced positive integer paise constraints (guarding against `bool` subclasses and non-integers), upper bound checks against outstanding due amount, and eligibility limited to paid cancelled/rejected orders.
5. **Refund Tracking:** Tracked `refund_due_paise` and `refunded_paise` separately; updated `payment_status` to `REFUNDED` only upon full settlement.
6. **Reconciliation:** Implemented deterministic reconciliation comparing internal and provider records by `order_id`, correctly reporting `matched`, `missing_from_provider`, `missing_from_internal`, `amount_mismatches`, and `status_mismatches`.
7. **Resilience:** Safely handled empty, malformed, non-dict, and missing fields.
8. **Optional Stretch:** Added `export_awaiting_refund_csv()` for operational CSV reporting.

## Files Changed and Why
- `service.py`: Fixed idempotency check, implemented refund eligibility and amount boundary validation, fixed reconciliation schema handling (`total_paise` vs `amount_paise`) and status comparison, and implemented stretch CSV export.
- `tests/test_regression.py`: Added 9 regression test suites protecting against payload conflicts, late payment arrivals, post-dispatch cancellations, dual mismatches, and validating against `data/records.json`.
- `approach.md`: Documented baseline analysis, root-cause investigations, architectural decisions, and verification evidence.
- `challenges.md`: Documented challenges including Python's `bool` subclassing trap, reconciliation schema differences, and dual-mismatch handling.
- `optimizations.md`: Documented optimizations including upfront idempotency guards and hash map reconciliation.
- `ORDER_FLOW_NOTES.md`: Provided full event sequence trace, edge cases, and architectural assumptions.
- `TESTING.md`: Provided environment details, test commands, edge-case table, and regression test catalog.

## Tests Run
- Baseline suite: `python3 -m pytest -q` -> 212 tests.
- Extended suite: `python3 -m pytest -q` -> 221 tests (all passed in 0.09s).
- Offline demo: `python3 -m main` -> verified clean reconciliation output.
- Synthetic dataset test: All 150 orders, 163 provider records, and 219 events from `data/records.json` reconciled without error.

## Assumptions
- Order totals and refund amounts are in integer paise (₹1 = 100 paise).
- Orders cannot be cancelled after dispatch or delivery.
- Replaying an event ID is an idempotent no-op regardless of the payload.

## Known Limitations
- State is held in-memory; distributed deployments would require distributed locking or relational database transactions.
