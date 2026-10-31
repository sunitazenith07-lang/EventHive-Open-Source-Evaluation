# Project notes

## Requirements completed
- **Event Lifecycle Processing:** Handled `payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, and `refund_processed`.
- **State Transition Guardrails:** Ensured cancellation requests arriving after dispatch (`OUT_FOR_DELIVERY` or `DELIVERED`) are strictly rejected.
- **Event Idempotency:** Guarded state mutation and `processed_event_ids` tracking using `event_id`, ensuring duplicated or replayed events cannot corrupt state.
- **Strict Monetary Boundaries:** Enforced positive integer paise validation (`type(amount) is int and not bool and amount > 0`) and restricted refunds to outstanding refundable balance (`refunded_paise + amount <= refund_due_paise`).
- **Partial and Complete Refunds:** Maintained partial refund state in `payment_status="PAID"`; only transitions to `"REFUNDED"` when full due amount has been processed.
- **Deterministic Reconciliation:** Unified amount key extraction (`amount_paise` vs `total_paise`), independently reporting amount mismatches, status mismatches, missing records, and matches in alphabetical order by order ID.
- **Defensive Error Handling:** Tolerates `None`, non-dictionary elements, missing keys, and unknown event types.
- **Optional Stretch Feature:** Implemented `export_awaiting_refund_csv` for reporting outstanding refund balances.

## Files changed and why
- `service.py`: Fixed idempotency logic, refund validation/eligibility, out-of-order payment confirmation, and deterministic reconciliation. Implemented stretch CSV report export.
- `tests/test_regression.py`: Added 14 regression tests protecting edge cases from `data/records.json` and the stretch feature.
- `approach.md`: Completed baseline exploration, root-cause investigation, and verification notes.
- `challenges.md`: Completed in-depth reflection on boolean-as-integer bugs, schema key variations, and dual-attribute mismatches.
- `optimizations.md`: Evaluated trade-offs for `deepcopy`, hash-map lookups, and future streaming generators.
- `TESTING.md`: Documented test environment, commands, edge case results, and regression test list.
- `ORDER_FLOW_NOTES.md`: Documented full event lifecycle example, three edge cases, and domain assumptions.
- `.github/PULL_REQUEST_TEMPLATE.md`: Populated pull request template with verified test counts and root-cause summaries.

## Tests run
- `python -m pytest -q`: 226 passed in 0.21s (0 failures, 0 errors, 0 skipped).
- `python -m main`: Verified offline reconciliation demo output cleanly categorizes `ORD-101` (matched), `ORD-102` (status mismatch), `ORD-103` (missing provider), and `ORD-104` (missing internal).
- `data/records.json` end-to-end replay: Processed 150 orders, 219 events, and 163 provider records without error.

## Assumptions
- Monetary values are non-negative integers representing paise (INR cents).
- Cancellation is permitted only from `PLACED` or `ACCEPTED` states.
- Refunds apply exclusively to paid orders that are cancelled or rejected.

## Known limitations
- The implementation operates in-memory; enterprise deployments across distributed worker nodes require database transaction isolation or distributed locks.
