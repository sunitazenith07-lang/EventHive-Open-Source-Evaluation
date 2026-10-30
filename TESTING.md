# TESTING.md — Required submission

## Test command and environment
-Python 3.14.7 (local), pytest 9.2.0. CI uses Python 3.11.
-Command: python -m pytest -q
-Before: 62 failed, 150 passed. Now: 264 passed (52 new).

## Edge-case evidence

| # | Case | Expected | Actual | Test |
|---|---|---|---|---|
| 1 | Refund event sent twice | Applied once | refunded 400 | test_replayed_refund_is_not_applied_twice |
| 2 | Same ID, new amount | Ignored | refunded 400 | test_replayed_id_with_conflicting_payload_is_ignored |
| 3 | Same ID on two orders | Only first refunded | X 500, Y 0 | test_event_id_reused_on_another_order_is_skipped |
| 4 | Cancel after dispatch | Ignored | OUT_FOR_DELIVERY | test_cancel_after_dispatch_is_ignored |
| 5 | Refund 0, -10, 0.5, True, "10", None | Ignored | refunded 0 | test_invalid_refund_amounts_are_ignored |
| 6 | Refund 1200, due 1000 | Ignored | refunded 0 | test_refund_cannot_exceed_amount_due |
| 7 | Refund 400 then 600 | PAID, then REFUNDED | PAID, then REFUNDED | test_partial_then_final_refund_marks_refunded |
| 8 | Payment after cancel | Total becomes due | due 1000 | test_payment_after_cancellation_creates_refund_due |
| 9 | total_paise vs amount_paise | Matched | matched | test_internal_total_paise_is_compared_with_provider_amount |
| 10 | Empty reconciliation | All lists empty | All empty | test_empty_reconciliation |

## Regression tests added
-52 cases in tests/test_regressions.py. No original test changed.

| Bug | Main tests |
|---|---|
| Duplicate events | test_replayed_refund_is_not_applied_twice |
| Unchecked refunds | test_partial_then_final_refund_marks_refunded |
| Status mismatch | test_amount_and_status_mismatch_reported_in_both_lists |
| total_paise vs amount_paise | test_internal_total_paise_is_compared_with_provider_amount |
| Unchecked payments | test_payment_after_full_refund_does_not_reset_status |
| Bad events and rows | test_non_dict_event_is_ignored, test_rows_without_order_id_are_reported_not_merged |
| ID checks (0, " ", True) | test_valid_event_ids_including_zero_are_applied, test_unusable_event_ids_are_ignored |
| ID reused across orders | test_event_id_reused_on_another_order_is_skipped |
| apply_events crashes | test_apply_events_reports_orders_without_usable_id |
| Weak "not mutated" test | test_input_order_and_nested_event_list_are_not_mutated |

## Remaining failures or limitations
-No failing tests.
-Out-of-order events are ignored.
-Two records with no amount look matched.
-payment_status isn't reconciled.
-24 dataset orders have impossible states; not flagged.
