# OrderOps architecture notes

## Source file map
- `models.py`: Defines `new_order`, the canonical constructor for order state representations with initialized keys (`order_id`, `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise`, `processed_event_ids`).
- `service.py`: Contains the primary event-processing engine (`apply_order_event`) and deterministic multi-criteria reconciliation function (`reconcile_orders`).
- `fixtures.py`: Provides mock orders and provider transactions for local testing and offline execution.
- `main.py`: Entry point for local demo, running reconciliation across sample fixtures and displaying categorizations.
- `data/records.json`: Synthetic dataset containing 150 internal orders, 163 provider records, 219 event examples, and 12 documented reconciliation edge cases.
- `tests/test_acceptance_matrix.py`: Acceptance test matrix covering status transitions, idempotency, refund eligibility, and reconciliation.
- `tests/test_contract.py`: Fundamental contract specifications.
- `tests/test_regression_edge_cases.py`: Extended regression test suite for boundary and real-world edge cases.

## Order state transitions
```
[PLACED] ---- restaurant_accepted ----> [ACCEPTED] ---- dispatch_started ----> [OUT_FOR_DELIVERY] ---- order_delivered ----> [DELIVERED]
   |                                         |
   +----- restaurant_rejected ----> [REJECTED]
   |                                         |
   +----- cancel_requested ------------------+-----> [CANCELLED]
```
- Orders in `OUT_FOR_DELIVERY` or `DELIVERED` ignore subsequent `cancel_requested` events.
- Rejection is valid only from `PLACED`.
- Dispatch can only start once the order has been `ACCEPTED`.

## Payment and refund state flow
```
[UNPAID] ---- payment_confirmed ----> [PAID]
                                        |
                 (Order CANCELLED / REJECTED triggers refund_due_paise)
                                        |
                 ---- refund_processed (amount <= outstanding) ---->
                                        |
                 (Partial refund: remains [PAID])
                 (Full refund: refunded_paise == refund_due_paise -> [REFUNDED])
```
- Amounts are strictly positive integers in paise (`1 INR = 100 paise`).
- Booleans, floats, negative values, and amounts exceeding outstanding refundable balance are rejected without corrupting state.

## Duplicate event strategy
- Every event processed with a non-null `event_id` is tracked in `processed_event_ids`.
- When an event arrives, `apply_order_event` checks if `event_id in processed_event_ids`.
- If already present, the function returns immediately without re-applying state transitions, mutating amounts, or duplicating `event_id` in the history.
- Events missing an `event_id` are executed safely once.

## Three edge cases I tested
1. **Cancellation Attempt Post-Dispatch:** An order in `OUT_FOR_DELIVERY` receiving `cancel_requested` preserves its status without modification or refund calculation.
2. **Replay With Conflicting Payload:** An event replayed with the same `event_id` but an inflated `amount_paise` is rejected by the idempotency gate, keeping the original state intact.
3. **Late Payment on Rejected Order:** A payment confirmed event arriving after restaurant rejection accurately triggers full `refund_due_paise` calculation.
