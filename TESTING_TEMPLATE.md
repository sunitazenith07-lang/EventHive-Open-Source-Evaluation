# Test notes — OrderOps

For at least five scenarios, record input, expected outcome, actual outcome, and the test or command used.

See complete details in [TESTING.md](TESTING.md).

| # | Case / input | Expected outcome | Actual outcome | Test or command used |
|---|---|---|---|---|
| 1 | Duplicate event replay (`payment_confirmed`) | Idempotent; no duplicate ID in `processed_event_ids` | `payment_status == 'PAID'`, `processed_event_ids == ['EV-001']` | `test_payment_event_replay_idempotent[EV-001]` |
| 2 | Boolean refund amount (`amount_paise=True`) | Rejected; refund remains 0 | `refunded_paise == 0` | `test_boolean_refund_amounts_are_rejected` |
| 3 | Cancellation post-dispatch (`OUT_FOR_DELIVERY`) | Ignored; status remains in transit | `status == 'OUT_FOR_DELIVERY'` | `test_cancel_after_dispatch_is_ignored` |
| 4 | Refund exceeding balance due (remaining 2000, attempted 2001) | Rejected; refund amount unchanged | `refunded_paise == 3000` | `test_refund_exceeding_remaining_due_is_rejected` |
| 5 | Simultaneous amount and status discrepancy | Reported in both mismatch categories | `amount_mismatches == ['O']`, `status_mismatches == ['O']` | `test_reconciliation_simultaneous_amount_and_status_mismatch` |
| 6 | Late payment after rejection | Rejection retained, payment marked PAID, full refund due set | `status == 'REJECTED'`, `payment_status == 'PAID'`, `refund_due_paise == 3000` | `test_late_payment_confirmed_on_rejected_order_sets_refund_due` |
