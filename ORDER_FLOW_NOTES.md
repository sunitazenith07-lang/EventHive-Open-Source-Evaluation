# Example order flow

> AI-assisted reference: this document records work performed by Codex, not an unaided student submission.

## Observed sequence

Start with `new_order("EXAMPLE", 1000)`: PLACED / UNPAID / due 0 / refunded 0.
All amounts below are integer paise. `evidence/walkthrough.json` is the actual output
from executing this sequence through the reference service.

| Step | Event | Expected order / payment / due / refunded | Actual result |
|---|---|---|---|
| 1 | p1: payment_confirmed | PLACED / PAID / 0 / 0 | Exactly as expected |
| 2 | c1: cancel_requested | CANCELLED / PAID / 1000 / 0 | Exactly as expected |
| 3 | r1: refund_processed, amount 400 | CANCELLED / PAID / 1000 / 400 | Exactly as expected |
| 4 | Replay r1, amount 400 | CANCELLED / PAID / 1000 / 400; history unchanged | Exactly as expected |
| 5 | r2: refund_processed, amount 600 | CANCELLED / REFUNDED / 1000 / 1000 | Exactly as expected |

The final processed IDs are `["p1", "c1", "r1", "r2"]`. The due amount remains
1000 throughout partial refund processing: it represents the original obligation.

## Edge cases verified

1. **Cancel after dispatch:** payment -> acceptance -> dispatch -> cancel. State
   remains OUT_FOR_DELIVERY, refund due remains 0. Actual result matched;
   `test_cancel_after_dispatch_does_not_create_refund_obligation` passed.
2. **Cumulative excess:** after refunding 400 of 1000, request 601. No additional
   amount is applied. Actual refunded amount remains 400;
   `test_partial_duplicate_conflicting_payload_and_completion` passed.
3. **Late payment:** unpaid cancellation/rejection -> payment confirmation. The
   order stays terminal and due becomes 1000. A valid refund completes payment.
   `test_late_payment_after_unpaid_terminal_event_establishes_due` passed.
4. **Conflicting replay:** reuse r1 with a different amount. Recorded ID prevents
   any second effect; the multi-step partial-refund regression passed.

## Assumptions and limitations

Cancellation is eligible from PLACED or ACCEPTED only. Restaurant rejection applies
only to PLACED, and delivery only to OUT_FOR_DELIVERY, matching the original matrix.
Payment processing is independent of food-order state. A late payment for a cancelled
or rejected order creates the refund obligation; it does not reopen the order.
Event IDs are scoped to an order. Recognized, addressed events with valid IDs are
consumed even when their requested change is rejected; unknown/malformed envelopes
are not consumed. This is a documented policy choice for replay safety.

The service records refund notifications; it does not send money or call a provider.
History is in memory and not safe for concurrent writers without an external atomic
store. See GUIDE.md for the complete error policy and other limitations.
