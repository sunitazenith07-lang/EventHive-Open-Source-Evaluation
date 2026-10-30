# OrderOps Architecture Notes

## 1. Source File Map

- `service.py`: Core domain logic for the food-delivery platform. Contains:
  - `apply_order_event(order: dict, event: dict) -> dict`: State transition engine, refund calculation, and event deduplication.
  - `reconcile_orders(internal: list[dict], provider: list[dict]) -> dict`: Reconciles internal records with third-party payment/delivery provider records.
  - `export_awaiting_refund_csv(orders: list[dict], filepath: str | None = None) -> str`: Operations utility to report orders awaiting refund settlement.
- `models.py`: Defines the canonical internal order schema dictionary via `new_order(order_id, total_paise, status="PLACED")`.
- `fixtures.py`: Provides synthetic internal and provider orders for offline local demonstration.
- `main.py`: Application entry point running offline reconciliation demonstration.
- `tests/test_contract.py`: Fundamental contract test suite ensuring immutability, basic transitions, and error rejection.
- `tests/test_acceptance_matrix.py`: Parametrized combinatorial matrix tests covering transitions, idempotency, refund eligibility, and reconciliation.
- `tests/test_regression_and_edge_cases.py`: Extended regression test suite for bug fixes, edge cases, type safety, and stretch features.

## 2. Order State Transitions

```
                    [PLACED]
                   /        \
  restaurant_accepted      restaurant_rejected
                 /            \
           [ACCEPTED]      [REJECTED] (Terminal)
            /       \
dispatch_started   cancel_requested
          /           \
[OUT_FOR_DELIVERY]  [CANCELLED] (Terminal)
        |
  order_delivered
        |
   [DELIVERED] (Terminal)
```

- **Cancellation Rules:** An order can be cancelled only while in `PLACED` or `ACCEPTED` status. Once dispatched (`OUT_FOR_DELIVERY` or `DELIVERED`), cancellation requests are ignored.
- **Terminal States:** `REJECTED`, `CANCELLED`, and `DELIVERED` are terminal. Out-of-order forward transitions (e.g., dispatch or acceptance on a rejected/cancelled order) are rejected.

## 3. Payment and Refund State Flow

- **Payment State:**
  - `UNPAID` (initial)
  - `PAID` (via `payment_confirmed`)
  - `REFUNDED` (via `refund_processed` when `refunded_paise == refund_due_paise`)
- **Refund Eligibility:**
  - Order must be in `REJECTED` or `CANCELLED` status.
  - Order `payment_status` must be `PAID`.
  - `refund_due_paise` must be strictly positive.
  - Refund amount must be a positive integer in paise (excluding booleans) and `amount <= refund_due_paise - refunded_paise`.
  - Partial refunds remain in `payment_status="PAID"`; only when cumulative `refunded_paise` reaches `refund_due_paise` does payment status become `REFUNDED`.

## 4. Duplicate Event Strategy

- Each event carries an `event_id`.
- The order dictionary maintains a list `processed_event_ids`.
- At the start of `apply_order_event`:
  - If `event_id` is non-null and already present in `processed_event_ids`, the function returns the unmodified order copy immediately.
  - Upon successful evaluation, `event_id` is appended to `processed_event_ids`.
- This ensures idempotency: replaying payment confirmations, cancellations, or refund disbursements causes zero side-effects.

## 5. Three Edge Cases Tested

1. **Post-Dispatch Cancellation Immunity:** Cancellation requests for orders in `OUT_FOR_DELIVERY` or `DELIVERED` do not alter status or trigger refunds.
2. **Boolean / Floating-Point Type Safety:** Validated against Python's `bool` subclassing of `int` (`isinstance(True, int) is True`), ensuring `True` and `False` are rejected rather than processed as 1 or 0 paise.
3. **Out-of-Order Payment and Rejection:** When restaurant rejection occurs before payment confirmation, late payment confirmation sets `payment_status="PAID"` and initializes `refund_due_paise=total_paise`, preserving refund eligibility.
