# Order flow notes

AI-assisted implementation and observations by Codex; not an individual-work declaration.

## Example verified by test_refund_sequence_and_replay
Order O has total 1000 paise. Refund due is the original obligation, not the remaining balance.

| Event | Expected order / payment / due / refunded | Actual |
|---|---|---|
| payment_confirmed p | PLACED / PAID / 0 / 0 | As expected |
| cancel_requested c | CANCELLED / PAID / 1000 / 0 | As expected |
| refund_processed r1, 400 | CANCELLED / PAID / 1000 / 400 | As expected |
| replay r1, 400 | CANCELLED / PAID / 1000 / 400 | As expected |
| refund_processed r2, 600 | CANCELLED / REFUNDED / 1000 / 1000 | As expected |
| payment_confirmed p2 | CANCELLED / REFUNDED / 1000 / 1000 | As expected |

## Edge cases
1. Cancellation after dispatch preserves OUT_FOR_DELIVERY: verified by existing cancellation test.
2. Late payment on an unpaid CANCELLED or REJECTED order establishes total refund due:
   verified for both states by test_late_payment_creates_refund_due.
3. Replaying an ID with a different payload does nothing:
   verified by test_duplicate_id_with_changed_payload_is_ignored.
4. Partial refunds retain PAID until the cumulative amount exactly equals due:
   verified by test_refund_sequence_and_replay.

## Assumptions and limitations
Acceptance/rejection starts only from PLACED; cancellation is allowed from PLACED or ACCEPTED;
dispatch requires ACCEPTED; delivery requires OUT_FOR_DELIVERY.
Event IDs are nonempty strings scoped to each order. An event may omit order_id because
the caller supplies its order; a supplied differing ID is rejected. Caller routes unknown IDs.
Recognized well-formed events are consumed even when their transition is ineligible;
there is no retry buffer for out-of-order events. Malformed events are not consumed.
Payment confirmations cannot reopen REFUNDED. Positive integer paise exclude booleans.
No stretch feature was added.
