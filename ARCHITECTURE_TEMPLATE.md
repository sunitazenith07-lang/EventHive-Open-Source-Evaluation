# OrderOps architecture notes

## Source file map
- `models.py`: defines the synthetic order record structure and the `new_order()` helper used to initialise an order with `order_id`, `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise`, and `processed_event_ids`.
- `service.py`: contains the state machine for lifecycle updates, idempotency checks, refund validation, and reconciliation logic.
- `fixtures.py`: provides sample internal and provider-order snapshots used by the offline demo and validation checks.
- `main.py`: runs the reconciliation demo and prints the generated report.
- `tests/`: contains contract, acceptance, and regression tests covering lifecycle transitions, malformed input handling, and reconciliation edge cases.
- `data/`: stores the larger synthetic order and event dataset used to model cancellations, rejections, duplicate receipts, and refund mismatches.

## Order state transitions
The service follows a constrained lifecycle model:

- `PLACED` is the initial state created by `new_order()`.
- `payment_confirmed` marks the order as paid without changing the order status.
- `restaurant_accepted` transitions `PLACED -> ACCEPTED`.
- `restaurant_rejected` transitions `PLACED -> REJECTED` and creates a refund obligation if the payment was already confirmed.
- `cancel_requested` is valid only while the order is `PLACED` or `ACCEPTED`; it moves the order to `CANCELLED` and sets `refund_due_paise` when paid.
- `dispatch_started` moves `ACCEPTED -> OUT_FOR_DELIVERY`.
- `order_delivered` moves `OUT_FOR_DELIVERY -> DELIVERED`.
- `refund_processed` applies only to eligible paid, cancelled/rejected orders and reduces the outstanding refund amount without exceeding the due balance.

The service intentionally refuses invalid transitions instead of mutating state silently. This is enforced by gating each event type on current status values and by rejecting invalid refund ranges.

## Payment and refund state flow
- `payment_status` starts as `UNPAID` and is updated to `PAID` when `payment_confirmed` is accepted.
- `refund_due_paise` tracks the maximum amount owed to the customer after a rejection or cancellation.
- `refunded_paise` stores the total amount actually returned.
- When `refunded_paise` reaches the due balance, `payment_status` is transitioned to `REFUNDED`.
- Refund processing rejects non-positive values, unsupported payment states, disallowed statuses, and amounts greater than the outstanding refundable balance.

This preserves the rule that partial refunds remain partial until the outstanding amount is fully settled.

## Duplicate event strategy
A duplicate event is detected using `event_id` and `processed_event_ids`. When the same `event_id` appears again, the event is ignored and the previous order/payment/refund state remains unchanged.

This protects against replay bugs and ensures the system remains idempotent even when the same event is delivered multiple times.

## Three edge cases I tested
1. Malformed event payloads such as `None`, `{}`, and `['bad']` are ignored without mutating the order.
2. Duplicate replay of the same `event_id` does not reapply a transition or refund.
3. Reconciliation with malformed rows, missing order IDs, or provider-only records does not crash and reports mismatches cleanly.

These scenarios align with the acceptance contract and are explicitly exercised by the regression tests in the repository.
