# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- **Python version:** Python 3.15.0
- **Command run:** `python -m pytest -q`
- **Actual test summary:** `222 passed in 0.50s` (212 existing acceptance/contract tests + 10 regression edge-case tests)

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Event replay idempotency: Replaying `payment_confirmed` with same `event_id` ("EV-000") | State unchanged; `processed_event_ids` contains `['EV-000']` exactly once without duplicate | Duplicate ignored; `processed_event_ids == ['EV-000']` | `test_payment_event_replay_idempotent[EV-000]` |
| 2 | Invalid refund payload types: `amount_paise = True`, `-10`, `0.5`, `"10"`, `None` | Refund ignored; `refunded_paise` remains 0; `payment_status` remains `PAID` | Ignored cleanly without modification or exception; `refunded_paise == 0` | `test_invalid_refund_amounts_are_ignored` |
| 3 | Over-limit partial refund: Order due 5000, first refund 4000, second refund 2000 | First refund accepted (4000); second exceeds remaining due (1000) and is rejected | `refunded_paise` is 4000; second refund ignored; status stays `PAID` | `test_refunds_cannot_exceed_due[4000-2000]` |
| 4 | Cancellation attempted after dispatch: Order in `OUT_FOR_DELIVERY` receives `cancel_requested` | Cancellation ignored; order stays in `OUT_FOR_DELIVERY`; no refund due generated | Status preserved as `OUT_FOR_DELIVERY`; `refund_due_paise == 0` | `test_cancellation_after_dispatch_preserves_state` |
| 5 | Late payment after restaurant rejection: Unpaid order rejected, then `payment_confirmed` arrives | Status remains `REJECTED`, `payment_status` becomes `PAID`, `refund_due_paise` set to full total | `status == "REJECTED"`, `payment_status == "PAID"`, `refund_due_paise == 7500` | `test_payment_confirmed_after_rejection` |
| 6 | Exact boundary amount: 1 paisa order placed, paid, cancelled, and refunded | Status `CANCELLED`, `refund_due_paise == 1`, refunded 1 paisa transitions to `REFUNDED` | `refunded_paise == 1`, `payment_status == "REFUNDED"` | `test_boundary_amounts_one_paisa` |
| 7 | Reconciliation with dual mismatch: Both amount and status mismatch for order ID | Order reported in both `amount_mismatches` and `status_mismatches`; not in `matched` | `report["amount_mismatches"] == ["ORD-BOTH"]`, `report["status_mismatches"] == ["ORD-BOTH"]` | `test_reconciliation_simultaneous_amount_and_status_mismatch` |

## Regression tests added
The following tests were created in `tests/test_regression_edge_cases.py` to prevent defects from returning:
1. `test_payment_confirmed_after_rejection`: Prevents losing refund due when payment notification arrives after rejection.
2. `test_payment_confirmed_after_cancellation`: Prevents losing refund due when payment arrives after customer cancellation.
3. `test_replay_with_conflicting_payload_is_ignored`: Prevents duplicate events with conflicting amounts from corrupting state.
4. `test_event_without_event_id_handled_safely`: Guarantees events without an `event_id` are processed safely without crashing.
5. `test_reconciliation_simultaneous_amount_and_status_mismatch`: Ensures orders with both amount and status differences appear in both mismatch lists.
6. `test_empty_and_malformed_records`: Protects against `None`, empty dicts, or unkeyed records in reconciliation and event processing.
7. `test_boundary_amounts_one_paisa`: Protects 1 paisa edge-case handling.
8. `test_cancellation_after_dispatch_preserves_state`: Guarantees dispatched orders cannot be cancelled retroactively.
9. `test_partial_refund_then_full_refund_sequence`: Protects multi-step partial refund accumulation.
10. `test_refund_attempt_on_delivered_order_rejected`: Prevents processing refunds on fulfilled orders.

## Remaining failures or limitations
- **Remaining failures:** None. All 222 tests pass cleanly with zero errors or failures.
- **Known limitations:**
  - Idempotency tracking uses an in-memory list per order dictionary, which is ideal for single-node / offline execution but should be backed by an external distributed store (e.g. Redis) in production.
  - Reconciliation expects records to be keyable by `order_id`; records with missing or `None` order IDs are ignored as malformed entries.
