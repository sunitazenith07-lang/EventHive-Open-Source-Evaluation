# OrderOps architecture notes

## Source file map
- `service.py`: Contains the core business logic. `apply_order_event` handles state transitions, idempotency, and refunds, while `reconcile_orders` compares internal and provider summaries.
- `models.py`: Helper module providing `new_order` to create clean internal order dictionaries.
- `fixtures.py`: Sample orders and provider summaries used by the offline demo in `main.py`.
- `data/records.json`: Synthetic dataset containing 150 orders, 163 provider records, and 219 event scenarios representing real-world food-delivery operational anomalies.
- `tests/`: Contains test suites: `test_acceptance_matrix.py` (transition matrices and bounds), `test_contract.py` (core contracts), and `test_regression.py` (our 9 new edge-case tests).

## Order state transitions
Orders progress along an explicit, guarded lifecycle:
1. `PLACED`: Initial state. Can transition to `ACCEPTED` via `restaurant_accepted`, `REJECTED` via `restaurant_rejected`, or `CANCELLED` via `cancel_requested`.
2. `ACCEPTED`: Restaurant accepted the order. Can transition to `OUT_FOR_DELIVERY` via `dispatch_started`, or `CANCELLED` via `cancel_requested`.
3. `OUT_FOR_DELIVERY`: Rider is on the way. Can transition to `DELIVERED` via `order_delivered`. Cancellations are strictly rejected at this stage.
4. `DELIVERED`, `CANCELLED`, `REJECTED`: Terminal states. No further status changes are permitted.

## Payment and refund state flow
- Payment begins as `UNPAID`. A `payment_confirmed` event sets it to `PAID`.
- If an order is rejected or cancelled while `PAID`, `refund_due_paise` is scheduled equal to `total_paise`.
- If an order was cancelled or rejected while unpaid and payment confirms late, `refund_due_paise` is updated upon payment confirmation so the customer is not left stranded.
- `refund_processed` decrements the remaining refundable balance (`refund_due_paise - refunded_paise`). Partial refunds maintain `payment_status="PAID"`. Once accumulated refunds equal `refund_due_paise`, payment status transitions to `REFUNDED`.

## Duplicate event strategy
- Idempotency is enforced using `processed_event_ids`.
- When an event arrives with an `event_id` already present in `processed_event_ids`, `apply_order_event` returns the order immediately without executing any logic or appending redundant IDs.
- Events with `event_id=None` are processed safely without appending `None` into the processed list.

## Three edge cases I tested
1. **Cancellation attempted after dispatch (`OUT_FOR_DELIVERY`):** Cancellation is ignored, preserving status and preventing invalid refund claims.
2. **Refund exceeding remaining due:** An incoming refund that exceeds `refund_due_paise - refunded_paise` is rejected completely rather than partially applied.
3. **Dual reconciliation mismatch:** Orders differing in both amount and status are reported in both `amount_mismatches` and `status_mismatches` and excluded from `matched`.
