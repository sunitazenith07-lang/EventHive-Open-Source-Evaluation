# Order flow notes

## Example sequence

A local probe started with `new_order('EXAMPLE', 1000)` and applied the sequence below. All amounts are integer paise. The columns show expected and observed results; `refund_due_paise` stays at the full liability rather than decreasing as refunds arrive.

| Step | Event ID / type / amount | Expected status / payment / due / refunded | Actual result |
|---|---|---|---|
| 0 | New order | PLACED / UNPAID / 0 / 0 | As expected |
| 1 | pay / payment_confirmed | PLACED / PAID / 0 / 0 | As expected |
| 2 | accept / restaurant_accepted | ACCEPTED / PAID / 0 / 0 | As expected |
| 3 | cancel / cancel_requested | CANCELLED / PAID / 1000 / 0 | As expected |
| 4 | r1 / refund_processed / 400 | CANCELLED / PAID / 1000 / 400 | As expected |
| 5 | r2 / refund_processed / 600 | CANCELLED / REFUNDED / 1000 / 1000 | As expected |
| 6 | Replay r2 / refund_processed / 600 | CANCELLED / REFUNDED / 1000 / 1000 | As expected; history also unchanged |
| 7 | late-pay / payment_confirmed | CANCELLED / REFUNDED / 1000 / 1000 | As expected; fresh ID recorded, payment unchanged |

The sequence's final history is `pay, accept, cancel, r1, r2, late-pay`.

## Tested edge cases

1. **Cancellation after dispatch.** An OUT_FOR_DELIVERY order receives `cancel_requested`. Expected and actual: it remains OUT_FOR_DELIVERY, with no new refund liability. The original cancellation test and transition matrix pass.
2. **Payment after unpaid cancellation/rejection.** Close an unpaid order, then confirm payment. Expected and actual: it remains closed, becomes PAID, and acquires due equal to its total. A subsequent full refund changes payment to REFUNDED. Covered by `test_late_payment_establishes_refund_due_for_unpaid_terminal_order` for both closed states.
3. **Partial, oversized and final refunds.** Against due 1000, apply 300, 200, 501 and 500. Expected and actual: cumulative refunds are 300, 500, 500 and 1000. The oversized payment is refused, and payment becomes REFUNDED only after the final 500. Covered by `test_partial_refunds_complete_only_at_full_due_and_keep_due_unchanged`.
4. **Replay after the state becomes eligible.** Refuse early dispatch, accept the order, then replay the original dispatch ID. Expected and actual: the order remains ACCEPTED. Recognized, addressed events are consumed once even when refused. Covered by `test_rejected_transition_is_recorded_and_cannot_apply_on_later_replay`.
5. **Conflicting payload under one ID.** Confirm payment, then reuse the same ID for cancellation. Expected and actual: no second effect. Covered by `test_conflicting_payload_cannot_reuse_a_processed_id`.

## Transition and refund assumptions

- Acceptance/rejection require PLACED. Cancellation requires PLACED or ACCEPTED. Dispatch requires ACCEPTED; delivery requires OUT_FOR_DELIVERY. Payment is independent of these lifecycle transitions, preserving the starter's accepted delivery behavior.
- Only a PAID order in CANCELLED or REJECTED may receive a refund. Valid paid cancellation/rejection creates full due; late payment on an unpaid closed order does the same.
- Every amount/counter must be an integer, excluding booleans. A refund must be positive and at most `refund_due_paise - refunded_paise`. Stored balances must satisfy `0 <= refunded <= due <= total`.
- Partial refunds leave payment PAID. Full refunds set REFUNDED exactly at the due amount. A payment notification never reverses REFUNDED.
- Event IDs are nonempty strings and are scoped to the supplied order's history. An optional explicit `event.order_id` must match; malformed/unknown envelopes leave the complete order unchanged. Recognized, addressed events with safe order accounting are recorded once, including refused transitions or refunds. A retry needing a different business action must have a fresh ID.
- Functions return independent copies and never mutate source records. The caller owns persistence and target routing. There is no global event registry, transaction lock or automatic reordering; out-of-order events are refused under the current state.
- Invalid historical accounting is preserved unchanged for investigation; the service does not invent a repair. Reconciliation accepts existing internal totals, compares amount/status separately, and flags conflicting duplicate fields deterministically. Unknown row IDs without a usable identifier cannot be reported and are skipped.

The full local suite passed with **301 tests**, including 89 added cases. Assistance and policy limitations are disclosed in `AI_USAGE.md`.
