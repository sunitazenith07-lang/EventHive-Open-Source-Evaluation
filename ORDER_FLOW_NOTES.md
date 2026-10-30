# ORDER_FLOW_NOTES.md

## 1. Example order-event sequence
Order `ORD-201`, total 45900 paise, created with `new_order("ORD-201", 45900)`. State is shown as `status / payment_status / refund_due_paise / refunded_paise`.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `p1` payment_confirmed | PLACED / PAID / 0 / 0 | PLACED / PAID / 0 / 0 |
| 2 | `a1` restaurant_accepted | ACCEPTED / PAID / 0 / 0 | ACCEPTED / PAID / 0 / 0 |
| 3 | `c1` cancel_requested | CANCELLED / PAID / 45900 / 0 (full total now due) | CANCELLED / PAID / 45900 / 0 |
| 4 | `r1` refund_processed 20000 | CANCELLED / PAID / 45900 / 20000 (partial stays PAID) | CANCELLED / PAID / 45900 / 20000 |
| 5 | `r1` replayed | no change (duplicate id) | CANCELLED / PAID / 45900 / 20000, ids not duplicated |
| 6 | `r2` refund_processed 30000 | ignored: only 25900 is outstanding | CANCELLED / PAID / 45900 / 20000 |
| 7 | `r3` refund_processed 25900 | CANCELLED / REFUNDED / 45900 / 45900 | CANCELLED / REFUNDED / 45900 / 45900 |
| 8 | `p2` payment_confirmed (late) | stays REFUNDED | CANCELLED / REFUNDED / 45900 / 45900 |
| 9 | `r4` refund_processed 1 | ignored: nothing outstanding | CANCELLED / REFUNDED / 45900 / 45900 |

To reproduce, run `python` from the repo root and paste:
```python
from models import new_order
from service import apply_order_event
o = new_order("ORD-201", 45900)
events = [("p1", "payment_confirmed", None), ("a1", "restaurant_accepted", None),
          ("c1", "cancel_requested", None), ("r1", "refund_processed", 20000),
          ("r1", "refund_processed", 20000), ("r2", "refund_processed", 30000),
          ("r3", "refund_processed", 25900), ("p2", "payment_confirmed", None),
          ("r4", "refund_processed", 1)]
for eid, kind, amt in events:
    e = {"event_id": eid, "type": kind}
    if amt is not None:
        e["amount_paise"] = amt
    o = apply_order_event(o, e)
    print(eid, kind, o["status"], o["payment_status"], o["refund_due_paise"], o["refunded_paise"])
```

## 2. Three edge cases
1. **Cancel after dispatch.** `ORD-202` (10000): payment, accepted, dispatch_started, then cancel_requested. Expected: the cancel is ignored. Actual: `OUT_FOR_DELIVERY / PAID / 0`, no refund due. Verified by `test_cancel_after_dispatch_is_ignored`.
2. **Over-limit refund, then the exact amount.** `ORD-203` (5000): payment, then restaurant_rejected, so 5000 is due. A refund of 5001 is ignored (`0 / PAID`); a refund of 5000 then gives `5000 / REFUNDED`. Verified by `test_refunds_cannot_exceed_due` and `test_two_partial_refunds_sum_to_full_and_complete_the_refund`.
3. **Refund arrives before the cancellation (known limitation).** `ORD-204` (5000): payment, then a 5000 refund while the order is still PLACED. Expected: the refund is not applicable yet. Actual: ignored (`PLACED / PAID / 0 / 0`) and the id `r1` is recorded, so the same event cannot be applied later. Verified by `test_rejected_refund_id_is_still_recorded_so_it_cannot_be_retried`.

Further cases are in `TESTING.md`: missing or invalid event ids, bool/float/string amounts, late payment after a refund, payment after a cancellation, and reconciliation with mixed or missing ids.

## 3. Assumptions and limitations
- Cancellation is allowed only from PLACED or ACCEPTED. Dispatch is allowed only from ACCEPTED, delivery only from OUT_FOR_DELIVERY.
- When a paid order is rejected or cancelled, `refund_due_paise` is the full `total_paise`. If payment is confirmed after the order is already rejected or cancelled, the refund due is recorded at that moment.
- Money is integer paise. Floats (even `1000.0`), strings, `None` and bools are rejected as refund amounts. An over-limit refund is ignored entirely, not trimmed.
- `payment_status` becomes REFUNDED only when `refunded_paise` equals `refund_due_paise`. A partial refund stays PAID.
- An event with a missing or unusable `event_id` is ignored. Any other event is recorded once seen, even if it changed nothing.
- Reconciliation compares `amount_paise` (falling back to `total_paise`) and `status`. An order that differs in both appears in both mismatch lists. Rows with no usable `order_id` are skipped, and the last of duplicate ids wins.
- Limitations: a refund notification that arrives before the cancellation is lost (edge case 3); statuses outside the lifecycle, such as `FAILED`, have no transitions; `order` must be a dict.