# ORDER_FLOW_NOTES.md

## 1. Example order-event sequence

Order `ORD-201`, `total_paise = 45900` (₹459.00), starting `PLACED / UNPAID`.

| Step | Event | Expected order / payment / refund state | Actual result |
|---|---|---|---|
| 1 | `e1 payment_confirmed` | PLACED / PAID / due 0, refunded 0 | `applied` → PLACED / PAID / 0 / 0 |
| 2 | `e2 restaurant_accepted` | ACCEPTED / PAID / 0 / 0 | `applied` → ACCEPTED / PAID / 0 / 0 |
| 3 | `e3 cancel_requested` (before dispatch) | CANCELLED / PAID / due 45900 / 0 | `applied` → CANCELLED / PAID / 45900 / 0 |
| 4 | `e4 refund_processed 20000` | partial refund: stays PAID / 45900 / 20000 | `applied` → CANCELLED / PAID / 45900 / 20000 |
| 5 | `e4` again (replay) | no change | `duplicate_event` → CANCELLED / PAID / 45900 / 20000 |
| 6 | `e5 refund_processed 30000` | rejected: 30000 > outstanding 25900 | `refund_exceeds_outstanding` → unchanged |
| 7 | `e6 refund_processed 25900` | full due reached → REFUNDED | `applied` → CANCELLED / REFUNDED / 45900 / 45900 |
| 8 | `e7 dispatch_started` | rejected: cancelled order cannot be dispatched | `invalid_transition` → unchanged |

Allowed status transitions (anything else is rejected and changes nothing):

```
PLACED --restaurant_accepted--> ACCEPTED --dispatch_started--> OUT_FOR_DELIVERY --order_delivered--> DELIVERED
PLACED --restaurant_rejected--> REJECTED
PLACED / ACCEPTED --cancel_requested--> CANCELLED
```

`payment_confirmed` and `refund_processed` change payment/refund fields only, never `status`.

**Refund rule:** when an order becomes CANCELLED or REJECTED while PAID, `refund_due_paise = total_paise`. Each `refund_processed` must be a positive `int` (not `bool`/`float`/`str`). It must also be ≤ `refund_due_paise − refunded_paise` and apply to a CANCELLED/REJECTED order that is PAID. `payment_status` becomes REFUNDED only when `refunded_paise == refund_due_paise`.

## 2. Three edge cases

1. **Cancellation after dispatch.** `payment_confirmed → restaurant_accepted → dispatch_started → cancel_requested → order_delivered` on `ORD-202` (12000 paise). Expected: the cancel is rejected, no refund is created, delivery still works. Actual: `cancel_requested` returns `invalid_transition`, the order stays OUT_FOR_DELIVERY with `refund_due_paise = 0`, then becomes DELIVERED. Verified by `test_cancel_after_dispatch_is_ignored`, `test_cancel_after_dispatch_reports_invalid_transition` and the transition matrix.
2. **Replayed refund notification.** The same `refund_processed` event id is applied twice to a paid, cancelled order. Expected: counted once. Actual: second call returns `duplicate_event`, `refunded_paise` stays 400, `processed_event_ids == ["r1"]`. The starter code produced `refunded_paise = 1200` for two 600-paise replays on a 1000 due, and marked the order REFUNDED. Verified by `test_replayed_refund_is_counted_once` and `test_replay_with_conflicting_payload_is_still_ignored`.
3. **Refund notification arrives before the order is eligible.** In `data/records.json`, `ORD-1007` (PLACED / PAID) receives `refund_processed 1000` *before* `restaurant_rejected`. Expected: the early refund is rejected, and the order ends REJECTED / PAID with 1000 due and 0 refunded, which the reconciliation catches. Actual: `refund_not_eligible`, then `applied` for the rejection → REJECTED / PAID / 1000 / 0. Because a rejected event is not recorded as processed, a later redelivery of the same refund event applies once. Verified by `test_rejected_refund_is_not_recorded_so_a_redelivery_can_apply_later`.

## 3. Assumptions and limitations

- **Cancellation eligibility:** only PLACED or ACCEPTED orders can be cancelled. OUT_FOR_DELIVERY and DELIVERED orders ignore `cancel_requested`.
- **Dispatch:** only an ACCEPTED order can be dispatched, and only an OUT_FOR_DELIVERY order can be delivered. Acceptance does not require payment, because the starter tests accept an UNPAID PLACED order.
- **Late payment:** a `payment_confirmed` that arrives after CANCELLED/REJECTED sets `refund_due_paise = total_paise`, because that money must go back.
- **Refund due vs refunded** are separate fields. Over-refunds are rejected whole, not capped, because silently capping would hide a provider/internal disagreement.
- **Event ids** must be non-empty strings and are tracked per order (`processed_event_ids`). The same id reused on a different order is treated as a different event.
- **Rejected events are not recorded.** This means an out-of-order event can be applied on redelivery. The trade-off is that re-running a whole stream can change an order once (ORD-1007 above). After that it reaches a fixed point, which is tested.
- Not handled: refunds for delivered orders (no event type for it), partial cancellations, and out-of-order detection beyond rejecting the transition.
