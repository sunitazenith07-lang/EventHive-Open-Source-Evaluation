# optimizations.md - Required submission

In short: the whole dataset already runs in about 1 ms, so I made no speed changes. I measured first, then kept the code simple.

## 1. Baseline and objective
-Goal: correct results first, then code that's easy to read.
-Data size: 150 orders and 219 events, with at most 4 events per order.
-Suspected slow spot: the duplicate check, because processed_event_ids is a list.

## 2. Options considered
1.Use a set for processed_event_ids
    -Faster lookups, but the tests expect a list and JSON can't store a set.
    -Measured: with 4000 IDs, the check takes 0.02 ms but copying the order takes 0.24 ms. The check isn't the slow part. Rejected.
2.Copy the order once per batch instead of once per event
    -Faster for long histories, but it needs a second code path. Real orders get at most 4 events. Rejected for now.
3.Use pandas
    -An extra install for an offline project, when dict and csv already work. Rejected.
4.Find orders with a dictionary keyed by order ID
    -Goes straight to the order instead of checking every one. Chosen. (Not measured.)

## 3. Changes implemented
-These are for clarity, not speed, so there's no before/after speed number.
1.One helper per rule: _refund_allowed, _valid_id and _amount.
    -Each rule is written once. Tests: test_invalid_refund_amounts_are_ignored, test_unusable_event_ids_are_ignored.
2.One shared function for bad and duplicate rows: _index_rows, used by reconcile_orders and apply_events.
    -Both follow the same rules. Tests: test_duplicate_order_id_is_reported_not_matched, test_apply_events_does_not_guess_between_duplicate_orders.
3.Return early for repeated, ID-less or malformed events.
    -Nothing is done twice. Tests: test_replayed_refund_is_not_applied_twice, test_non_dict_event_is_ignored.
4.Quality-of-life additions (see approach.md Section 6): bad events ignored, bad and duplicate rows reported, apply_events for batches, and the awaiting-refund CSV.
-Measured with time.perf_counter on Python 3.14.7: whole dataset about 1 ms; all 264 tests about 0.15 s.

## 4. Trade-offs
-Copying the order on every event keeps the caller's data safe, but twice the events take about four times as long (1000 / 2000 / 4000 events on one order: 36 / 136 / 530 ms).
-Reporting problems instead of crashing adds more lists to the output, but nothing is lost silently.
-Skipping duplicated orders never picks the wrong copy, but those orders wait until the data is fixed.
-The strict ID rule blocks mistakes like " " or True, but could reject an unusual real ID.

## 5. Further improvements
-If orders get thousands of events: copy once per batch and keep a set next to the list. Check with the same timing and all tests.
-Queue out-of-order events and apply them when the order is ready. Check with tests that shuffle the event order.
-Report records with no amount as invalid rows (see challenges.md). Check with a test where both amounts are missing.
