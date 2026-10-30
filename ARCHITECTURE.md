# OrderOps architecture notes

## Source file map
- `models.py`: Defines `new_order()`, initializing the canonical dictionary structure for synthetic order records with default fields (`status`, `payment_status`, `refund_due_paise`, `refunded_paise`, `processed_event_ids`).
- `service.py`: Contains primary business logic:
  - `apply_order_event(order, event)`: Pure functional state transition engine. Accepts an order and event, validates transitions and idempotency, and returns an updated order dictionary without mutating input objects.
  - `reconcile_orders(internal, provider)`: Independent reconciliation engine. Resolves schema divergence (`total_paise` vs `amount_paise`), groups discrepancies into deterministic sets, and sorts keys.
  - `export_awaiting_refund_csv(orders)`: Stretch utility generating CSV formatted reports of orders with pending refunds.
- `fixtures.py` & `main.py`: Sample data fixtures and offline CLI runner demonstrating local reconciliation.
- `data/records.json`: Synthetic evaluation dataset containing 150 internal orders, 163 provider records, 219 event examples, and edge case specifications.
- `tests/`: Acceptance matrix (`test_acceptance_matrix.py`), contract specifications (`test_contract.py`), and regression tests (`test_regression.py`).

## Order state transitions
```
               [PLACED]
              /   |    \
   restaurant_    |     cancel_requested
   rejected       |      \
         v        |       v
    [REJECTED]    |   [CANCELLED]
                  v        ^
             restaurant_   | cancel_requested
             accepted      |
                  v        |
             [ACCEPTED] ---+
                  |
            dispatch_started
                  |
                  v
          [OUT_FOR_DELIVERY]
                  |
            order_delivered
                  |
                  v
             [DELIVERED]
```

## Payment and refund state flow
```
   [UNPAID]
      |
   payment_confirmed
      |
      v
    [PAID] -------------------------------+
      |                                   |
 (order REJECTED/CANCELLED)               |
      |                                   |
 refund_due_paise = total_paise           |
      |                                   |
      +---> [refund_processed]            |
                  |                       |
            (partial refund)              |
                  |                       |
           refunded_paise < due           |
                  |                       |
                  v                       v
               [PAID]                  [PAID]
                  |
            (full refund)
                  |
           refunded_paise == due
                  |
                  v
              [REFUNDED]
```

## Duplicate event strategy
- Every event ingested contains an optional `event_id`.
- The order state maintains `processed_event_ids: list[str]`.
- Upon event invocation, if `event_id` is present and already exists in `processed_event_ids`, `apply_order_event` immediately returns the unmodified copy of the order.
- This guarantees:
  - Idempotent payment confirmations.
  - Idempotent restaurant acceptance/rejection.
  - Safe replay of refund events preventing duplicate financial disbursements.

## Three edge cases I tested
1. **Cancellation After Dispatch:**
   - Order reaches `OUT_FOR_DELIVERY` after `dispatch_started`.
   - Customer submits `cancel_requested`.
   - State engine ignores cancellation; order remains `OUT_FOR_DELIVERY` without refund due.
2. **Strict Currency Type Guarding (Boolean Rejection):**
   - In Python, `isinstance(True, int)` is true. Passing `amount_paise=True` into a refund processor could add 1 paise to the ledger.
   - Enforced `type(amount) is int and amount > 0`, ensuring booleans and non-integers are discarded.
3. **Dual-Dimension Reconciliation Mismatches:**
   - Provider and internal record differ in both amount (e.g. 5000 vs 6000 paise) and status (e.g. `PLACED` vs `CANCELLED`).
   - Engine records the order in both `amount_mismatches` and `status_mismatches`, and ensures it is excluded from `matched`.
