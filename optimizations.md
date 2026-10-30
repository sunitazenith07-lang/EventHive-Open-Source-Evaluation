# optimizations.md - Required submission

In short: the code already runs the whole dataset in about 1 ms, so I didn't make speed changes. I focused on making it correct and easy to read, and I measured before deciding.

## 1. Baseline and objective
-The main goal was correctness: no double refunds, no impossible states and no crashes on bad input.
-The second goal was code that's easy to read and explain, with each rule written in one place.
-Before thinking about speed, I checked how big the data really is:
    -records.json has 150 orders, 219 events and 163 provider records.
    -Each order gets at most 4 events (1.4 on average).
-The one part that looked slow was the duplicate check, because processed_event_ids is a list and Python has to look through all of it.

## 2. Options considered
1.Store processed_event_ids as a set instead of a list
    -Benefit: checking "have I seen this event before?" is faster in a set.
    -Rejected: the tests expect a list, and a set can't be saved in JSON.
    -I measured it first. With 4000 IDs stored, the check takes about 0.02 ms, but copying the order takes about 0.24 ms, more than 10 times longer. So the check isn't the slow part.
2.Copy the order once per batch instead of once for every event
    -Benefit: much faster for an order with thousands of events.
    -Rejected for now: it needs a second way of applying events, which means more code and more chances for bugs. Real orders only get up to 4 events.
3.Use a library like pandas
    -Rejected: it adds an extra install to an offline project, and Python's own dict and csv module already do the job. It would also be harder to explain.
4.Look up orders in a dictionary by order ID
    -Chosen: apply_events and reconcile_orders go straight to the right order instead of checking every order in a list.
    -Not measured. This is just how dictionaries work.

## 3. Changes implemented
-These changes are about clarity and not repeating code, not speed. I didn't measure a before/after speedup because speed wasn't the goal.

1.One helper for each rule
    -Change: _refund_allowed (when a refund is allowed), _valid_id (what counts as an ID) and _amount (reads amount_paise, or total_paise if it's missing).
    -Reason: each rule is written once, so it's easy to explain and can't end up different in two places.
    -Tests: test_invalid_refund_amounts_are_ignored, test_refund_eligibility_matrix, test_unusable_event_ids_are_ignored, test_internal_total_paise_is_compared_with_provider_amount.
2.One function for bad and duplicate rows
    -Change: _index_rows is used by both reconcile_orders and apply_events.
    -Reason: both follow the same rules for missing and repeated order IDs, without copying code.
    -Tests: test_rows_without_order_id_are_reported_not_merged, test_duplicate_order_id_is_reported_not_matched, test_apply_events_reports_orders_without_usable_id, test_apply_events_does_not_guess_between_duplicate_orders.
3.Stop early when there's nothing to do
    -Change: apply_order_event returns straight away for a repeated event, an event with no usable ID, or something that isn't an event at all.
    -Reason: nothing is done twice, and the order can't be changed by mistake.
    -Tests: test_replayed_refund_is_not_applied_twice, test_event_without_id_is_ignored, test_non_dict_event_is_ignored.
4.Quality-of-life additions (details in approach.md Section 6)
    -Bad events are ignored instead of crashing the code.
    -Rows with no order ID, and order IDs that appear twice, are reported instead of being merged or guessed.
    -apply_events runs a whole batch of events and reports anything it skipped, so nobody has to write their own loop.
    -awaiting_refund_csv lists the customers who are still owed money (the one stretch item).

MEASUREMENTS
-Method: timed with Python's time.perf_counter on my laptop (Python 3.14.7). Times change a little between runs, so I repeated each one.
-Whole dataset (apply_events, reconcile_orders and the CSV report): about 1 ms (middle value of 50 runs).
-All 264 tests: about 0.15 s.

## 4. Trade-offs
1.Copying the order on every event
    -Good: the caller's order is never changed. test_input_order_and_nested_event_list_are_not_mutated checks this.
    -Cost: each event copies the whole history, and the history grows by one every time. So twice the events takes about four times as long:
        -1000 events on one order: about 36 ms
        -2000 events: about 136 ms
        -4000 events: about 530 ms
    -This only matters with thousands of events on one order, which this data never has.
2.Reporting problems instead of crashing or guessing
    -Good: nothing is lost silently, and someone can find and fix the bad rows.
    -Cost: the reports have more lists to read.
3.Skipping orders whose ID appears twice
    -Good: the code never picks the wrong copy.
    -Cost: those orders aren't processed until the data is fixed.
4.A strict rule for IDs
    -Good: things like " ", True or 1.5 can't be used as IDs by mistake.
    -Cost: an unusual but real ID format would be rejected.

## 5. Further improvements
1.If orders start getting thousands of events, copy the order once per batch and keep a set of IDs next to the list.
    -How I'd check it: run the same timing again (twice the events should then take about twice as long), and all tests, including the "input not changed" test, must still pass.
2.Save events that arrive in the wrong order (like dispatch before accept) and apply them once the order is ready.
    -How I'd check it: new tests where the same events arrive in a different order should end in the same state.
3.Report records with no amount as invalid rows, like rows with no order ID (see challenges.md).
    -How I'd check it: a test where both sides have no amount should no longer show as matched.
