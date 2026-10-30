# TESTING.md — Required submission

## Test command and environment
-Python version: 3.14.7 (on my laptop, inside .venv). GitHub Actions runs the same tests on Python 3.11.
-pytest version: 9.2.0
-Command run: python -m pytest -q (from the repository root)
-Actual test summary:
    -Before any change: 62 failed, 150 passed
    -Now: 264 passed in 0.14s (the 212 original tests plus 52 regression tests I added)
-Demo: python -m main runs without errors. It shows ORD-101 as matched, ORD-102 as a status mismatch, and the awaiting-refund report.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Same refund event sent twice (r1, 400 paise) | Refund applied only once | refunded_paise = 400, processed_event_ids = ["r1"] | test_replayed_refund_is_not_applied_twice |
| 2 | Same event ID with a different amount (r1: 400, then r1: 600) | Second one ignored | refunded_paise = 400 | test_replayed_id_with_conflicting_payload_is_ignored |
| 3 | One refund event ID sent to two orders, X and Y | Only X is refunded; Y's event is reported | X = 500, Y = 0, cross_order_duplicates = [1] | test_event_id_reused_on_another_order_is_skipped |
| 4 | cancel_requested on an order that is OUT_FOR_DELIVERY | Order stays OUT_FOR_DELIVERY | status = OUT_FOR_DELIVERY | test_cancel_after_dispatch_is_ignored |
| 5 | Refund amounts 0, -10, 0.5, True, "10" and None | All ignored | refunded_paise = 0 for every one | test_invalid_refund_amounts_are_ignored (15 amounts) |
| 6 | Refund of 1200 when only 1000 is due | Ignored | refunded_paise = 0 | test_refund_cannot_exceed_amount_due |
| 7 | Refund 400, then 600, when 1000 is due | PAID after the first, REFUNDED after the second | PAID, then REFUNDED with refunded_paise = 1000 | test_partial_then_final_refund_marks_refunded |
| 8 | Payment arrives after the order was cancelled | Payment recorded and the full amount becomes due | payment_status = PAID, refund_due_paise = 1000 | test_payment_after_cancellation_creates_refund_due |
| 9 | Event with no event_id; event with event_id 0 | No ID: ignored. ID 0: applied | No ID: stays UNPAID. ID 0: becomes PAID | test_event_without_id_is_ignored, test_valid_event_ids_including_zero_are_applied |
| 10 | ORD-101 is 45900 as total_paise (ours) and amount_paise (provider) | Matched | matched = ["ORD-101"], amount_mismatches = [] | test_internal_total_paise_is_compared_with_provider_amount, python -m main |
| 11 | Amount 100 vs 90 and status PLACED vs CANCELLED | Reported in both mismatch lists | amount_mismatches = ["A"], status_mismatches = ["A"], matched = [] | test_amount_and_status_mismatch_reported_in_both_lists |
| 12 | Empty internal and provider lists | Every list in the report is empty | All lists empty | test_empty_reconciliation |
| 13 | All 219 events in records.json applied to the 150 orders | No order refunded more than it's due | Passed for all 150 orders | test_dataset_refunds_never_exceed_due |

## Regression tests added
-All of these are in tests/test_regressions.py (52 test cases). I didn't change or delete any of the original tests.

1.Duplicate events were applied again
    -test_replayed_refund_is_not_applied_twice, test_replayed_id_with_conflicting_payload_is_ignored, test_event_without_id_is_ignored
2.Refunds weren't checked
    -test_partial_then_final_refund_marks_refunded, test_refund_after_full_refund_is_rejected, test_refund_without_amount_is_rejected, test_rejected_refund_id_is_still_recorded, test_full_paid_rejection_lifecycle
3.Status mismatches weren't reported
    -test_amount_and_status_mismatch_reported_in_both_lists, test_status_mismatches_are_sorted
4.Our total_paise was never compared with the provider's amount_paise
    -test_internal_total_paise_is_compared_with_provider_amount, test_internal_total_paise_mismatch_is_reported
5.Payment events weren't checked
    -test_payment_after_full_refund_does_not_reset_status, test_payment_after_cancellation_creates_refund_due
6.Quality-of-life additions
    -test_non_dict_event_is_ignored, test_rows_without_order_id_are_reported_not_merged, test_duplicate_order_id_is_reported_not_matched, test_apply_events_routes_by_order_id_and_reports_unknown, test_dataset_refunds_never_exceed_due, test_awaiting_refund_csv_lists_only_outstanding_orders_sorted, test_awaiting_refund_csv_empty_input_has_header_only
7.Follow-up fixes
    -The original "input not changed" test couldn't see changes to the list of event IDs: test_input_order_and_nested_event_list_are_not_mutated. I checked it against a broken copy of the code; the original test still passed, but the new one failed.
    -An ID of 0 was rejected, while " ", True and lists were accepted or crashed the code: test_valid_event_ids_including_zero_are_applied, test_unusable_event_ids_are_ignored, test_order_id_zero_is_reconciled, test_unhashable_order_ids_in_reconciliation_are_reported, test_unhashable_event_order_id_is_unrouted
    -One event ID could refund two different orders: test_event_id_reused_on_another_order_is_skipped, test_event_id_processed_by_another_order_before_the_batch_is_skipped, test_same_order_replay_is_not_reported_as_cross_order
    -apply_events crashed on bad orders, guessed between duplicate orders, and handed back the caller's own objects: test_apply_events_reports_orders_without_usable_id, test_apply_events_does_not_guess_between_duplicate_orders, test_apply_events_returns_copies_not_the_callers_orders

## Remaining failures or limitations
-No failing tests: 264 passed on Python 3.14.7. GitHub Actions runs them on Python 3.11, and the result shows on the pull request.
-Events that arrive in the wrong order (for example dispatch before accept) are ignored, not saved for later.
-If both records have no amount field, both read as None and look matched (see challenges.md).
-Reconciliation compares order status only, not payment_status.
-24 of the 150 orders in records.json are in states the rules can't produce (for example ACCEPTED but REFUNDED with nothing refunded). The code doesn't flag these.
-Applying thousands of events to one order gets slow, because each event copies the whole history (see optimizations.md). Real orders get at most 4 events.
