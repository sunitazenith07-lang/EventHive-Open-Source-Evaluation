# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
SETUP
-Ran the following commands to initialize the repo and get setup:
1.Forked the repo from git and cloned it
    -cd E:\Aaryaman\Open_Source_Eval
    -git clone https://github.com/<AaryaVaarya>OrderOps-Open-Source-Evaluation.git
2.Set upstream to open pull request
    -git remote add upstream https://github.com/<original-owner>/OrderOps-Open-Source-Evaluation.git
    -git remote -v
3.Created virtual environment
-Already in .gitignore so it won't be committed
    -python -m venv .venv
    -.venv\Scripts\Activate.ps1
4.Getting pytest file to record baseline
    -python -m pip install --upgrade pip
    -python -m pip install -r requirements-dev.txt
    -python -m pytest --version
5.Recording baseline in baseline.txt
    -python -m pytest -q | Tee-Object baseline.txt
6.Creating the working branch
    -git checkout -b fix-order-refund-logic
    -git status
7.Added baseline.txt in .gitignore and checked using
    -git check-ignore -v baseline.txt

TEST_RESULT
-62 failed,150 passed.
Bugs can be reduced to the following sources.
    1.Duplicate events aren’t ignored
        -When an even tis run again, it's ID is added to processed_events_id a second time.
    2.refund_processed doesn’t validate anything.
        -Bad amounts are accepted
        -Ineligible orders are returned
        -There's no cap to the refunds
    3.Status Mismatch
        -order status is not being reported as mismatched if the status on two ends is different


- Demo/output observed (`python -m main`, before any change):
```
matched: []
missing_from_provider: ['ORD-103']
missing_from_internal: ['ORD-104']
amount_mismatches: ['ORD-101', 'ORD-102']
status_mismatches: []
```
Two things looked wrong. ORD-101 is 45900 paise on both sides but was reported as an amount mismatch. ORD-102 is `ACCEPTED` internally and `CANCELLED` at the provider, but `status_mismatches` was empty. The second matched baseline bug 3. The first was a fourth bug that no visible test covered (Issue 4 below).

## 2. Codebase understanding
FILES I LOOKED AT
1.service.py
    -Has all the logic: apply_order_event for order updates and reconcile_orders for comparing records.
2.models.py
    -new_order() creates an internal order and stores its amount as total_paise.
3.fixtures.py and main.py
    -Demo data. Provider records use amount_paise instead of total_paise.
4.Test files
    -test_contract.py and test_acceptance_matrix.py show what the correct behaviour should be.
5.data/records.json
    -Sample orders, provider records and events. Some events are messy, with missing or reused IDs and amounts in the wrong type.

HOW THE CODE WORKS
-An order starts as placed and can be accepted, sent out for delivery and delivered.
-It can be rejected or cancelled before delivery. If it was already paid, the full amount becomes due for refund.
-apply_order_event applies one event to a copy of the order and records the event's ID.
-reconcile_orders compares our orders with the provider's by order ID.

HOW I CHECKED MY UNDERSTANDING
-Read the test files and matched each failing test to the part of service.py it was testing.
-The status change tests were already passing, so the bugs were around them, not in them.
-Printed the keys in records.json, which is how I noticed total_paise vs amount_paise.

## 3. Investigation and implementation strategy
-Fixed one bug at a time, ran all the tests after each fix and made a separate commit for each.

1.Duplicate events
    -The same event run twice was recorded twice.
    -The list of processed IDs was only added to, never checked.
    -Fixed it by skipping an event if its ID was already processed. Events with no ID are also skipped.
2.Refund validation
    -Refunds of zero, negative numbers, decimals and True were all accepted, and None crashed the code.
    -Refunds also went through on orders that weren't cancelled, rejected or paid.
    -Added a helper that only allows a refund if the amount is a positive whole number, the order is eligible, and it doesn't go over the amount due.
    -True had to be checked separately, because Python treats it as the number 1.
3.Status mismatch
    -Orders with different statuses on each side were still reported as matched.
    -The code only compared amounts, never statuses.
    -Now amount and status are checked separately, and an order only counts as matched if both agree.
4.Amount mismatch in the demo
    -All tests passed, but the demo still showed ORD-101 as an amount mismatch even though the amounts were the same.
    -Our orders use total_paise and the provider uses amount_paise, so our amount was read as empty.
    -Added a helper that reads whichever of the two is there.
5.Payment had no checks
    -A payment event could mark an already refunded order as paid again.
    -A payment after a cancellation never set a refund amount, so the customer couldn't be refunded.
    -Payment now only works on unpaid orders, and a payment after a cancellation sets the refund due.

## 4. Implementation decisions
CHANGES
-All changes are in service.py and no function names or inputs changed, so nothing else needed editing.
-Put the refund rules in one helper to keep that part of the code short and readable.

THINGS I DECIDED NOT TO DO
-Reducing a refund that's too big: the tests expect it to be ignored, and changing the amount would hide a real problem.
-Not recording rejected events: each event ID should only ever be processed once.
-Accepting amounts like "10": amounts should be whole numbers in paise, not text.
-Changing the data files to one amount name: easier and safer to make reconciliation handle both.

ASSUMPTIONS
-Events with no ID are ignored, since duplicates can't be checked without one.
-Unknown event types do nothing.
-An order is only marked refunded once the full amount due has been refunded.
-Reconciliation compares order status, not payment status.

## 5. Verification
TESTS
-Didn't change any of the existing tests.
-Added 14 new tests in tests/test_regressions.py for the cases I fixed, like repeated refunds, missing event IDs, partial refunds, payments after cancellation and the total_paise issue.

TEST_RESULT
-Baseline: 62 failed, 150 passed.
-After fixing duplicates: 41 failed.
-After fixing refunds: 8 failed.
-After fixing status mismatch: all passing.
-Final, with the new tests: 226 passed.

EDGE CASES CHECKED
-Ran all the events in records.json and no order was refunded more than it was due.
-Ran reconciliation on the full dataset and it worked without crashing.

KNOWN LIMITATIONS
-If one side has the same order ID twice, only the last one is kept.
-Events that arrive in the wrong order are ignored, not saved for later.
-The duplicate check gets slower as more events are processed.