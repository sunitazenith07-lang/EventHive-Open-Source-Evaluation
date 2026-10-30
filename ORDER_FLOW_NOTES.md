# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence

Starting order: `new_order("ORD-DEMO", 1500)` — status `PLACED`, payment `UNPAID`, refund due 0 paise, refunded 0 paise.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` (`demo-1`) | `PLACED` / `PAID` / due 0 / refunded 0 | `PLACED` / `PAID` / due 0 / refunded 0 |
| 2 | `restaurant_rejected` (`demo-2`) | `REJECTED` / `PAID` / due 1,500 / refunded 0 | `REJECTED` / `PAID` / due 1,500 / refunded 0 |
| 3 | `refund_processed`, 500 paise (`demo-3`) | `REJECTED` / `PAID` / due 1,500 / refunded 500 | `REJECTED` / `PAID` / due 1,500 / refunded 500 |
| 4 | `refund_processed`, 1,000 paise (`demo-4`) | `REJECTED` / `REFUNDED` / due 1,500 / refunded 1,500 | `REJECTED` / `REFUNDED` / due 1,500 / refunded 1,500 |

The four-event sequence was executed directly against `apply_order_event`; each actual state matched the expected state.

## 2. Three edge cases

1. **Cancellation after dispatch.** Input: order status `OUT_FOR_DELIVERY`, followed by `cancel_requested`. Expected: keep `OUT_FOR_DELIVERY`; do not mark the order cancelled. Actual: status remained `OUT_FOR_DELIVERY`. Test: `test_cancel_after_dispatch_is_ignored` in `tests/test_contract.py`.

2. **Duplicate refund notification.** Input: eligible cancelled order with a 1,000-paise due; deliver the same event ID with a 600-paise refund twice. Expected: apply only once. Actual: `refunded_paise` remained 600 and the event ID appeared once. Test: `test_duplicate_refund_event_does_not_apply_twice` in `tests/test_regressions.py`.

3. **Cumulative refund exceeds due.** Input: eligible rejected order with a 1,000-paise due; process 700 paise, then request 301 paise. Expected: reject the second request because only 300 paise remains. Actual: the total stayed 700 and payment stayed `PAID`. Test: `test_cumulative_refund_cannot_exceed_due` in `tests/test_regressions.py`.

## 3. Assumptions and limitations

- `restaurant_accepted` is valid only from `PLACED`; `restaurant_rejected` is valid only from `PLACED`.
- Customer cancellation is permitted only from `PLACED` or `ACCEPTED`. A cancellation request after dispatch or delivery is ignored.
- Dispatch starts only from `ACCEPTED`; delivery moves only from `OUT_FOR_DELIVERY` to `DELIVERED`.
- A refund is eligible only when the order is `REJECTED` or `CANCELLED` and payment status is `PAID`.
- Refund values must be positive integer paise (boolean, floating-point, string, `None`, list, and dictionary values are rejected). A refund cannot exceed `refund_due_paise - refunded_paise`.
- `payment_status` becomes `REFUNDED` only when `refunded_paise` exactly reaches `refund_due_paise`. A partial refund leaves it `PAID`.
- A late `payment_confirmed` event for an already rejected or cancelled order sets its refund due to the order total, provided the total is a positive integer amount.
- Events need a non-empty event ID to be processed. Unknown event types, malformed event types, and events explicitly naming a different order ID are ignored. A recognized event ID is consumed once, even when its transition or refund payload is invalid; a later delivery with that ID is ignored.
- Reconciliation compares internal `total_paise` with provider `amount_paise` (and supports `amount_paise` on internal rows for direct summary inputs). Amount and status differences are reported independently. Missing amount/status values are treated as discrepancies.
- The function assumes at most one authoritative record per order ID per side. Duplicate IDs currently use the last row; malformed rows or rows without usable IDs are skipped. Persisting the event ledger and reporting duplicate source records would require a broader storage/reporting contract.
