# Order flow notes

Complete this during the evaluation:
- **Example order event sequence:**
  1. `payment_confirmed` -> status: `PLACED`, payment_status: `PAID`
  2. `restaurant_accepted` -> status: `ACCEPTED`, payment_status: `PAID`
  3. `cancel_requested` -> status: `CANCELLED`, refund_due_paise: 5000, payment_status: `PAID`
  4. `refund_processed` (2000) -> status: `CANCELLED`, refunded_paise: 2000, payment_status: `PAID`
  5. `refund_processed` (3000) -> status: `CANCELLED`, refunded_paise: 5000, payment_status: `REFUNDED`
- **Expected states:**
  Order states follow: `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`. Pre-dispatch cancellation or restaurant rejection moves orders to terminal `CANCELLED` or `REJECTED` states.
- **Refund calculation rule:**
  `outstanding = refund_due_paise - refunded_paise`. An incoming refund amount must be a positive integer where `0 < amount <= outstanding`. Partial refunds preserve `PAID` status; when `refunded_paise == refund_due_paise`, payment status becomes `REFUNDED`.
- **Three tested edge cases:**
  1. Post-dispatch cancellation attempt is rejected; order remains in `OUT_FOR_DELIVERY`.
  2. Duplicate event replay with conflicting payload is ignored by the idempotency gate.
  3. Late payment on a rejected order updates payment status to `PAID` and sets `refund_due_paise` to `total_paise`.
- **Known limitations:**
  Deduplication is stored within the order payload in-memory. High-volume systems require an indexed transactional store.
