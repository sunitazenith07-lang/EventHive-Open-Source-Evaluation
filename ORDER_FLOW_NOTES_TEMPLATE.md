# Order flow notes

Complete this during the evaluation:
- Example order event sequence: Order ORD-501 (65000 paise): `payment_confirmed` -> `restaurant_accepted` -> `cancel_requested` -> partial `refund_processed` (30000 paise) -> final `refund_processed` (35000 paise) -> `REFUNDED`.
- Expected states: PLACED -> ACCEPTED -> CANCELLED (refund due: 65000) -> CANCELLED (paid, refunded: 30000) -> CANCELLED (refunded: 65000, payment: REFUNDED).
- Refund calculation rule: Outstanding = `refund_due_paise` - `refunded_paise`. If `isinstance(amount, int)` and `not isinstance(amount, bool)` and `0 < amount <= Outstanding`, `refunded_paise += amount`.
- Three tested edge cases:
  1. Cancellation requested after dispatch (`OUT_FOR_DELIVERY`) is rejected.
  2. Late payment confirmed on previously rejected/cancelled order sets `refund_due_paise`.
  3. Replay of cumulative refund exceeding outstanding balance is ignored.
- Known limitations: In-memory `processed_event_ids` list requires distributed set/DB constraint in high-scale production.

See full documentation in [ORDER_FLOW_NOTES.md](ORDER_FLOW_NOTES.md).
