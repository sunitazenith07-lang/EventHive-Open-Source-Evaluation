# ORDER_FLOW_NOTES.md — Order lifecycle evidence

## 1. Example order-event sequence

I ran the following sequence against `new_order("FLOW-1", 1000)`. Amounts are integer paise.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` (`e1`) | `PLACED`, `PAID`, due 0, refunded 0 | `PLACED`, `PAID`, due 0, refunded 0 |
| 2 | `restaurant_accepted` (`e2`) | `ACCEPTED`, `PAID`, due 0, refunded 0 | `ACCEPTED`, `PAID`, due 0, refunded 0 |
| 3 | `cancel_requested` (`e3`) | `CANCELLED`, `PAID`, due 1000, refunded 0 | `CANCELLED`, `PAID`, due 1000, refunded 0 |
| 4 | `refund_processed` (`e4`, 1000 paise) | `CANCELLED`, `REFUNDED`, due 1000, refunded 1000 | `CANCELLED`, `REFUNDED`, due 1000, refunded 1000 |

## 2. Three edge cases

1. **Cancel after dispatch:** an `OUT_FOR_DELIVERY` order receiving `cancel_requested` stays `OUT_FOR_DELIVERY`. Verified by `test_cancel_after_dispatch_is_ignored` and the transition matrix.
2. **Duplicate partial refund notification:** applying the same 400-paise refund event twice leaves `refunded_paise` at 400 and stores the event ID once. Verified by `test_duplicate_refund_event_is_idempotent`.
3. **Refund exceeds remaining due:** a refund above the remaining due is ignored, and accumulated refunds stay within the due amount. Verified by `test_refund_cannot_exceed_amount_due`, `test_invalid_refund_amounts_are_ignored`, and `test_refunds_cannot_exceed_due`.

## 3. Assumptions and limitations

- Cancellation is accepted only from `PLACED` or `ACCEPTED`; cancellation after dispatch does not change the order state.
- Restaurant rejection is accepted from `PLACED`; dispatch is accepted from `ACCEPTED`; delivery is accepted from `OUT_FOR_DELIVERY`.
- A refund is eligible only for a paid order in `CANCELLED` or `REJECTED` state with a positive refund due. `refunded_paise` accumulates partial refunds and payment status becomes `REFUNDED` only when the due is fully met.
- Event IDs are non-empty strings. Unsupported event types and missing/malformed event fields do not change order state.
- State is in memory only. Persistence, concurrency, and live payment-provider behavior are not implemented or tested.
