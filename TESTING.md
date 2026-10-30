# TESTING.md — Required submission

## Test command and environment
-Python: 3.14.7 (local .venv), pytest 9.2.0. GitHub Actions uses Python 3.11.
-Command: python -m pytest -q
-Result: before any change 62 failed, 150 passed. Now 264 passed (212 original + 52 new).

## Edge-case evidence

| # | Case / input | Expected | Actual | Test |
|---|---|---|---|---|
| 1 | Same refund event sent twice (400) | Applied once | refunded = 400 | test_replayed_refund_is_not_applied_twice |
| 2 | Same event ID, new amount (400, then 600) | Second one ignored | refunded = 400 | test_replayed_id_with_conflicting_payload_is_ignored |
| 3 | One refund event ID sent to orders X and Y | Only X refunded | X = 500, Y = 0 | test_event_id_reused_on_another_order_is_skipped |
| 4 | Cancel after dispatch | Stays OUT_FOR_DELIVERY | OUT_FOR_DELIVERY | test_cancel_after_dispatch_is_ignored |
| 5 | Refund amounts 0, -10, 0.5, True, "10", None | All ignored | refunded = 0 | test_invalid_refund_amounts_are_ignored |
| 6 | Refund 1200 when 1000 is due | Ignored | refunded = 0 | test_refund_cannot_exceed_amount_due |
| 7 | Refund 400, then 600 (1000 due) | PAID, then REFUNDED | PAID, then REFUNDED | test_partial_then_final_refund_marks_refunded |
| 8 | Payment after cancellation | Full amount becomes due | refund_due = 1000 | test_payment_after_cancellation_creates_refund_due |
| 9 | ORD-101: 45900 as total_paise vs amount_paise | Matched | matched = ["ORD-101"] | test_internal_total_paise_is_compared_with_provider_amount |
| 10 | Empty input to reconciliation | All lists empty | All empty | test_empty_reconciliation |

## Regression tests added
-All in tests/test_regressions.py (52 cases). No original test was changed or deleted.

| Defect fixed | Main tests |
|---|---|
| Duplicate events applied again | test_replayed_refund_is_not_applied_twice, test_event_without_id_is_ignored |
| Refunds not checked | test_partial_then_final_refund_marks_refunded, test_refund_without_amount_is_rejected |
| Status mismatches not reported | test_amount_and_status_mismatch_reported_in_both_lists |
| total_paise never compared with amount_paise | test_internal_total_paise_is_compared_with_provider_amount |
| Payment events not checked | test_payment_after_full_refund_does_not_reset_status |
| Bad events and bad rows (QoL) | test_non_dict_event_is_ignored, test_rows_without_order_id_are_reported_not_merged |
| ID 0 rejected, odd IDs accepted | test_valid_event_ids_including_zero_are_applied, test_unusable_event_ids_are_ignored |
| One event ID refunding two orders | test_event_id_reused_on_another_order_is_skipped |
| apply_events crashing or sharing objects | test_apply_events_reports_orders_without_usable_id, test_apply_events_returns_copies_not_the_callers_orders |
| Starter "not mutated" test too weak | test_input_order_and_nested_event_list_are_not_mutated |

## Remaining failures or limitations
-No failing tests locally. The Python 3.11 result shows on the pull request.
-Out-of-order events are ignored, not saved.
-Two records with no amount both read as None and look matched.
-Reconciliation compares order status, not payment_status.
-24 dataset orders are in impossible states (e.g. ACCEPTED but REFUNDED). The code doesn't flag them.
