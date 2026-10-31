# OrderOps architecture notes

## Source file map
- `models.py`: Defines `new_order(order_id, total_paise, status="PLACED")` returning the canonical dictionary representation for internal order entities.
- `service.py`: Contains primary business logic:
  - `apply_order_event(order, event)`: Handles lifecycle transitions, payment updating, refund processing, and event deduplication idempotently.
  - `reconcile_orders(internal, provider)`: Compares internal order records against provider reports to identify matches, missing items, status discrepancies, and amount discrepancies.
  - `summarise_orders_by_state(orders)`: Aggregates order count and total paise grouped by lifecycle and payment state (`STATUS:PAYMENT_STATUS`).
  - `_extract_amount(order)`: Private helper resolving field name asymmetry between `total_paise` (internal) and `amount_paise` (provider).
- `fixtures.py`: Provides synthetic test datasets (`sample_orders`, `sample_provider_orders`) for local verification.
- `main.py`: Command-line entry point demonstrating offline order reconciliation output.
- `tests/`:
  - `test_contract.py`: Contract unit tests verifying event application, immutability, idempotency, and state transitions.
  - `test_acceptance_matrix.py`: Parameterized acceptance matrix testing state machine behavior, refund eligibility bounds, and reconciliation logic.
  - `test_regression.py`: Targeted regression tests covering boolean type safety, field name asymmetry, and simultaneous amount/status mismatches.

## Order state transitions
Valid state flow follows strict monotonic progression:
- **Happy Path**: `PLACED` $\rightarrow$ `ACCEPTED` $\rightarrow$ `OUT_FOR_DELIVERY` $\rightarrow$ `DELIVERED`.
- **Rejection Path**: `PLACED` $\rightarrow$ `REJECTED` (triggered by `restaurant_rejected`).
- **Cancellation Path**: `PLACED` or `ACCEPTED` $\rightarrow$ `CANCELLED` (triggered by `cancel_requested`).
- **Terminal Guards**:
  - `restaurant_accepted` is ignored unless current status is `PLACED`.
  - `cancel_requested` is ignored once an order reaches `OUT_FOR_DELIVERY` or `DELIVERED`.
  - Invalid, out-of-sequence, or unrecognized event types leave order status unmutated.

## Payment and refund state flow
- **Initial State**: New orders begin with `payment_status = "UNPAID"`, `refund_due_paise = 0`, and `refunded_paise = 0`.
- **Payment Arrival**:
  - `payment_confirmed` updates `payment_status` to `"PAID"`.
  - If payment arrives for an order already in `REJECTED` or `CANCELLED` status, `refund_due_paise` is populated with the full order total.
- **Refund Eligibility**:
  - Order status must be `REJECTED` or `CANCELLED`.
  - Payment status must be `PAID`.
  - `refund_due_paise` must be $> 0$.
- **Refund Processing (`refund_processed`)**:
  - Validates that `amount_paise` is strictly an integer (`type(amount) is int`, rejecting booleans), positive ($> 0$), and $\le$ remaining balance (`refund_due_paise - refunded_paise`).
  - Increments `refunded_paise` by the refund amount.
  - Updates `payment_status` to `"REFUNDED"` when cumulative `refunded_paise == refund_due_paise`. Partial refunds leave `payment_status` as `"PAID"`.

## Duplicate event strategy
- Deduplication relies on `processed_event_ids: list` stored on each order dictionary.
- Before evaluating event rules, `apply_order_event` performs an early idempotency check:
  ```python
  event_id = event.get("event_id")
  if event_id is not None and event_id in out["processed_event_ids"]:
      return out