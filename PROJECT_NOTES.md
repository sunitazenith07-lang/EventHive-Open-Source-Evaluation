# Project Notes — OrderOps

## Requirements Completed

1. **Event Processing:** Implemented support for all 7 required event types: `payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, and `refund_processed`.
2. **Valid State Transitions:** Enforced strict state transitions; post-dispatch cancellations (`OUT_FOR_DELIVERY` or `DELIVERED`) are ignored.
3. **Idempotency:** Implemented event deduplication via `event_id` and `processed_event_ids`, preventing duplicate events from altering state.
4. **Integer Currency & Bound Checks:** Ensured all amounts use integer paise; rejected non-positive, non-integer, and boolean amounts; verified refunds do not exceed outstanding refundable balance.
5. **Refund Tracking:** Tracked `refund_due_paise` and `refunded_paise` separately; kept partial refunds in `PAID` status, transitioning to `REFUNDED` only when the full due amount is disbursed.
6. **Reconciliation Engine:** Matched internal and provider summaries deterministically by `order_id`; separately and accurately populated `matched`, `missing_from_provider`, `missing_from_internal`, `amount_mismatches`, and `status_mismatches`; handled both `total_paise` and `amount_paise` keys.
7. **Malformed Input Resilience:** Safely handled None, empty dicts, missing fields, and unknown event types without corrupting state or crashing.
8. **Stretch Feature:** Implemented `export_awaiting_refund_csv` for operations teams.

## Files Changed and Why

- `service.py`: Fixed idempotency check, refund eligibility logic, amount validations, reconciliation comparisons, and added `export_awaiting_refund_csv`.
- `tests/test_regression_and_edge_cases.py`: Added 10 regression tests for all fixes, edge cases, type-safety, and stretch feature.
- `approach.md`: Completed required technical investigation and strategy document.
- `challenges.md`: Completed compulsory debugging and obstacle analysis document.
- `optimizations.md`: Completed required performance and architectural trade-offs document.
- `TESTING.md`: Completed required testing summary, edge-case table, and verification evidence.
- `ORDER_FLOW_NOTES.md`: Completed required event flow walkthrough, edge cases, and assumptions.
- `ARCHITECTURE.md`: Created detailed architecture and state transition reference.

## Tests Run

- Baseline: `python -m pytest -q` -> `62 failed, 150 passed in 0.64s`
- Final: `python -m pytest -q` -> `222 passed in 0.33s`
- Offline Demo: `python -m main` -> Clean deterministic reconciliation matching expectations.

## Assumptions

- Cancellations are restricted to `PLACED` and `ACCEPTED` states.
- Rejection and cancellation require prior or subsequent payment confirmation to become eligible for refund.
- Currency is strictly in non-negative integer paise.

## Known Limitations

- Events lacking an `event_id` cannot be deduplicated using the idempotency mechanism.
- Reconciliation assumes distinct order IDs per dataset. Duplicate order IDs in a single input list overwrite prior occurrences during dictionary construction.
