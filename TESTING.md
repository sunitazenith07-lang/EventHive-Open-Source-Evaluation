# TESTING.md — Required submission

## Test command and environment
-Python 3.14.7 (local), pytest 9.2.0. CI uses Python 3.11.
-Command: python -m pytest -q
-Before: 62 failed, 150 passed. Now: 286 passed (74 new).

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
-74 cases in tests/test_regressions.py. No original test changed. The most important:

| Bug | Test |
|---|---|
| Duplicate events | test_replayed_refund_is_not_applied_twice |
| Unchecked refunds | test_partial_then_final_refund_marks_refunded |
| Status mismatch | test_amount_and_status_mismatch_reported_in_both_lists |
| total_paise vs amount_paise | test_internal_total_paise_is_compared_with_provider_amount |
| ID reused across orders | test_event_id_reused_on_another_order_is_skipped |
| Null or text amounts on an order | test_refund_on_order_with_broken_amounts_is_ignored |

## Remaining failures or limitations
-No failing tests.
-Out-of-order events are ignored.
-Two records with no amount look matched.
-payment_status isn't reconciled.
-24 dataset orders have impossible states; not flagged.
