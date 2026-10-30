# Project Notes — OrderOps Evaluation

## Requirements completed
1. **Event Processing:** Successfully handles `payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, and `refund_processed`.
2. **State Machine Validation:** Strictly enforces valid transitions; cancellations after dispatch or delivery are safely ignored.
3. **Idempotency via `event_id`:** Deduplicates replayed events across payment, cancellation, rejection, and refunds without state pollution.
4. **Integer Paise Accounting:** Protects refund amounts against invalid types (including Python booleans `True`/`False`), floats, negatives, and over-refund attempts.
5. **Two-Stage Refund Tracking:** Accurately separates `refund_due_paise` and `refunded_paise`; partial refunds remain `PAID`; payment flips to `REFUNDED` only when full liability is settled.
6. **Deterministic Reconciliation:** Matches internal orders and provider summaries in $O(N + M)$ time; correctly categorizes missing provider records, missing internal records, amount mismatches, and status mismatches.
7. **Malformed Input Robustness:** Safely handles empty lists, non-dict payloads, missing IDs, and unexpected event types.
8. **Operational Stretch Work:** Added `summarize_orders_by_state` providing distribution metrics across lifecycle states.

---

## Files changed and why
- **`service.py`**: Corrected state transitions, idempotency checks, refund validation, and reconciliation logic; added `summarize_orders_by_state`.
- **`tests/test_regression_and_edge_cases.py`**: Added 10 comprehensive regression tests verifying edge cases.
- **`approach.md`**: Completed 5-mark mandatory document covering baseline results, codebase flow, root causes, decisions, and verification.
- **`challenges.md`**: Completed 5-mark COMPULSORY document detailing the boolean subclass trap, schema asymmetry, and dual reconciliation mismatches.
- **`optimizations.md`**: Completed 5-mark mandatory document evaluating architecture patterns, data structures, trade-offs, and measured speedup (~76% test time reduction).
- **`TESTING.md`**: Completed required test record with real test run data, 6 documented edge cases, and regression test catalog.
- **`ORDER_FLOW_NOTES.md`**: Completed challenge-specific order flow sequence, expected vs actual states, assumptions, and edge cases.
- **`ARCHITECTURE_TEMPLATE.md`**: Completed architectural mapping, state transition diagrams, and payment flows.

---

## Tests run
- **Baseline:** `python -m pytest -q` -> `62 failed, 150 passed in 1.87s` (total 212 tests).
- **Final:** `python -m pytest -q` -> `222 passed in 0.45s` (all 212 existing tests + 10 new regression tests, 0 failures).
- **Offline Demo:** `python -m main` executed successfully with expected reconciliation breakdown.

---

## Assumptions
- Monetary quantities are integer values measured in paise.
- Cancellation eligibility closes upon restaurant dispatch.
- Orders rejected or cancelled while unpaid will initiate refund due if late payment subsequently clears.

---

## Known limitations
- Event history is maintained in an in-memory list per order; in ultra-high scale deployments, uniqueness should be delegated to persistent primary key constraints or distributed key-value stores.
