# Order flow notes

Example order: new_order("FLOW-1", 1200); all amounts are integer paise.

| Event | Expected / observed state | Payment and refund |
| --- | --- | --- |
| payment_confirmed / evt-1 | PLACED | PAID, due 0, refunded 0 |
| restaurant_accepted / evt-2 | ACCEPTED | PAID, due 0, refunded 0 |
| cancel_requested / evt-3 | CANCELLED | PAID, due 1200, refunded 0 |
| refund_processed / evt-4, 500 paise | CANCELLED | PAID, due 1200, refunded 500 |
| refund_processed / evt-5, 700 paise | CANCELLED | REFUNDED, due 1200, refunded 1200 |

The event handler returns a copied order; callers must use the returned value for the next event. Refund amounts in these notes assume each notification has a unique event ID.

## Assumptions
- Only a paid cancelled/rejected order is eligible for a refund.
- Delivery dispatch locks out customer cancellation in this simplified lifecycle.
- Provider reconciliation summaries use order_id, amount_paise, and status.
- The project is an offline simulation; no external payment processor is called.

## Edge cases
1. Replaying evt-4 does not add the 500 paise a second time.
2. A cancellation after dispatch_started leaves the order OUT_FOR_DELIVERY and creates no refund due.
3. A refund of 701 paise after 500 of 1200 has been refunded is rejected because only 700 remains.
4. A provider record with the right amount and a different status appears in status_mismatches.
