# Test notes

For at least five scenarios, record input, expected outcome, actual outcome, and the test or command used.

| # | Scenario / Input | Expected Outcome | Actual Outcome | Test / Command |
|---|---|---|---|---|
| 1 | Idempotent duplicate event replay (`EV-000`) | Ignored without duplicate append in `processed_event_ids` | Duplicate event ignored; event ID recorded once | `test_payment_event_replay_idempotent` |
| 2 | Invalid refund payload (`amount_paise = True`) | Ignored without incrementing `refunded_paise` | Ignored; `refunded_paise == 0` | `test_invalid_refund_amounts_are_ignored` |
| 3 | Over-limit refund (`due = 5000`, `attempt = 5001`) | Ignored; amount exceeds due amount | Ignored; `refunded_paise == 0` | `test_refunds_cannot_exceed_due` |
| 4 | Cancellation requested after dispatch (`OUT_FOR_DELIVERY`) | Status remains `OUT_FOR_DELIVERY`; cancellation ignored | Status unchanged as `OUT_FOR_DELIVERY` | `test_cancellation_after_dispatch_preserves_state` |
| 5 | Dual mismatch in reconciliation (amount and status) | Order reported in both `amount_mismatches` and `status_mismatches` | Order placed in both mismatch categories; not in matched | `test_reconciliation_simultaneous_amount_and_status_mismatch` |
