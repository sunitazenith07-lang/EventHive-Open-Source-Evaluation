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

Failures grouped by test (`python -m pytest -q`, counting parametrised cases):

| Failing test | Cases | Root cause |
|---|---|---|
| `test_payment_event_replay_idempotent` | 20 | duplicates |
| `test_duplicate_event_is_idempotent` | 1 | duplicates |
| `test_invalid_refund_amounts_are_ignored` | 13 | refund validation |
| `test_refund_eligibility_matrix` | 10 | refund validation |
| `test_refunds_cannot_exceed_due` | 7 | refund validation |
| `test_refund_requires_eligible_order` / `_must_be_positive` / `_cannot_exceed_amount_due` | 3 | refund validation |
| `test_reconciliation_status_mismatch_matrix` | 7 | status mismatch |
| `test_reconcile_reports_status_difference` | 1 | status mismatch |

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
- Important files and functions inspected:
    - `service.py`: `apply_order_event(order, event)` (the state machine) and `reconcile_orders(internal, provider)`. All the logic is here.
    - `models.py`: `new_order()` builds an internal order. It stores the amount as **`total_paise`**.
    - `fixtures.py` / `main.py`: demo data. Internal rows come from `new_order()`; provider rows are hand-written dicts that use **`amount_paise`**.
    - `tests/test_contract.py` (12 tests) and `tests/test_acceptance_matrix.py` (200 parametrised cases): these define correct behaviour.
    - `data/records.json`: 150 orders (`total_paise`), 163 provider records (`amount_paise`), 219 events. Of those events, 7 have no `event_id`, 10 IDs are reused, 10 have type `unexpected_event`, and `amount_paise` values include `None`, `bool`, `float` and `str`.
    - `.github/workflows/tests.yml`: runs `python -m main`, then pytest on Python 3.11, and stays red while any test fails.
- Order lifecycle or data flow traced:
```
PLACED --restaurant_accepted--> ACCEPTED --dispatch_started--> OUT_FOR_DELIVERY --order_delivered--> DELIVERED
PLACED --restaurant_rejected--> REJECTED
PLACED / ACCEPTED --cancel_requested--> CANCELLED        (not allowed after dispatch)

payment:  UNPAID --payment_confirmed--> PAID --refunds sum to refund_due--> REFUNDED
refund_due_paise = total_paise when a PAID order becomes REJECTED/CANCELLED
```
  `apply_order_event` deep-copies the order, applies one event, and appends the `event_id` to `processed_event_ids`. `reconcile_orders` builds a dict per side keyed by `order_id` and walks the sorted union of keys.
- How I confirmed my understanding:
    - I read every assertion in both test files and mapped each failing test to a branch in `service.py` (table in Section 1).
    - The transition-matrix tests (26 cases) already passed, which confirmed the status transitions themselves were correct and the problems were around them.
    - I loaded `records.json` in a Python shell and printed the key sets for each section. That is how I found the `total_paise` / `amount_paise` difference.

## 3. Investigation and implementation strategy
I fixed one root cause at a time, ran the full suite after each, and committed each fix separately (failure count in each commit message).

- **Issue 1: Duplicate events are re-applied (62 → 41 failing)**
    - *Symptom:* `test_payment_event_replay_idempotent` expected `processed_event_ids == ["EV-000"]` but got `["EV-000", "EV-000"]`.
    - *Hypothesis:* the function writes `processed_event_ids` but never reads it.
    - *Evidence:* the only use of the list was the `append` at the end of the function.
    - *Fix:* return the unchanged copy if `event_id` is already in the list. I also ignore events with a missing or empty `event_id`. Otherwise every ID-less event shares the key `None`, so the first one would be applied and every later one silently dropped. And a replayed ID-less refund could never be detected.
- **Issue 2: `refund_processed` accepts anything (41 → 8 failing)**
    - *Symptom:* refunds of `0`, `-10`, `True`, `0.5` and `5001` were added. Refunds on `PLACED` and `UNPAID` orders were applied. `None` would crash with `TypeError` on `+=`.
    - *Hypothesis:* the branch has no guards at all. It adds `event.get("amount_paise", 0)` and marks `REFUNDED` on `>=`.
    - *Evidence:* `test_invalid_refund_amounts_are_ignored[True]` failed with `refunded_paise == 1`. That showed `bool` passes an `isinstance(x, int)` check, because `bool` is a subclass of `int`.
    - *Fix:* a `_refund_allowed()` helper checks four things: the amount is an `int` but not a `bool`; the amount is greater than 0; the order is `CANCELLED`/`REJECTED` and `PAID`; and `amount <= refund_due_paise - refunded_paise`. `REFUNDED` is now set only on `==`, so partial refunds stay `PAID`.
- **Issue 3: Status differences reported as matched (8 → 0 failing)**
    - *Symptom:* `test_reconcile_reports_status_difference` had `status_mismatches == []`.
    - *Evidence:* the `else` after the amount check went straight to `matched`. `status` was never compared.
    - *Fix:* compute `amount_ok` and `status_ok` separately. Append to each mismatch list on its own, and to `matched` only when both are OK. An order that differs in both ways appears in both lists; `records.json`'s edge-case catalog lists "amount and status mismatches individually and together".
- **Issue 4: Every internal order is an amount mismatch (found from the demo; all tests already passed)**
    - *Symptom:* after Issue 3, all 222 tests passed, but the demo still showed `amount_mismatches: ['ORD-101', ...]` with 45900 on both sides.
    - *Hypothesis:* the tests pass `amount_paise` on both sides, but real internal orders don't have that key.
    - *Evidence:* `new_order()` and all 150 orders in `records.json` use `total_paise`, so `a.get("amount_paise")` was `None`.
    - *Fix:* an `_amount()` helper reads `amount_paise` if present, otherwise `total_paise`. Demo after: `matched: ['ORD-101']`, `amount_mismatches: []`.
- **Issue 5: `payment_confirmed` has no guard (found by reading the code)**
    - A payment event with a new ID could flip a `REFUNDED` order back to `PAID`.
    - A payment arriving after a cancellation left `refund_due_paise = 0`, so the customer's money could never be refunded.
    - *Fix:* only `UNPAID → PAID`. If the order is already `CANCELLED`/`REJECTED`, set `refund_due_paise = total_paise`.

## 4. Implementation decisions
- Main changes and why:
    - All changes are in `service.py`, and the function signatures are unchanged, so `main.py` and the tests need no edits.
    - The refund rules live in one named helper (`_refund_allowed`) because there are four separate conditions. Putting it in the `elif` condition matches how the other branches are written.
- Alternatives considered and why rejected:
    - *Clamp an oversized refund to the outstanding amount*: rejected. `test_refunds_cannot_exceed_due` expects it to be ignored, and silently changing a provider's amount would hide a real discrepancy.
    - *Don't record the ID of a rejected event*: rejected. It would let a "fixed" event reuse an ID, which breaks the rule that an `event_id` is processed once. Now every event with an ID is recorded once, whether or not it changed state.
    - *Accept a numeric string like `"10"`*: rejected. The tests expect it to be ignored, and requirement 4 says integer paise.
    - *Change `models.py` / `fixtures.py` to use `amount_paise`*: rejected. That changes the data model and `records.json` uses `total_paise`; it's better for reconciliation to accept both.
- Assumptions:
    - An event with no `event_id` can't be made idempotent, so it is ignored.
    - Unknown event types are a no-op, but their ID is still recorded.
    - A refund only counts toward `REFUNDED` when it exactly reaches `refund_due_paise`.
    - Reconciliation compares `status` (order status), not `payment_status`.

## 5. Verification
- Tests added or changed:
    - No existing test was edited.
    - Added `tests/test_regressions.py` (14 tests): replayed refund; replayed ID with a different amount; missing/`None`/empty ID; partial-then-final refund; refund after full refund; refund with no amount; rejected-refund ID recorded; full paid-reject-refund lifecycle; amount+status both mismatched; sorted status mismatches; `total_paise` vs `amount_paise` (match and mismatch); payment after full refund; payment after cancellation.
- Commands run and actual results (`python -m pytest -q` after each commit):

| Commit | Result |
|---|---|
| Baseline | 62 failed, 150 passed |
| Issue 1: idempotency | 41 failed, 174 passed |
| Issue 2: refund validation | 8 failed, 212 passed |
| Issue 3: status mismatch | 222 passed |
| Issue 4: `total_paise` | 224 passed |
| Issue 5: payment guard | **226 passed** |

- Edge cases verified:
    - I ran every event in `records.json` through `apply_order_event` against its order. No order ended with `refunded_paise > refund_due_paise`, and 7 events with no matching order were skipped.
    - Reconciling the full dataset gave 107 matched, 12 missing from provider, 25 missing from internal, 20 amount mismatches and 12 status mismatches, with no crash.
- Remaining failures or known limitations:
    - No failing tests.
    - `reconcile_orders` keeps only the last row when one side has duplicate `order_id`s.
    - A record with no `order_id` is grouped under `None`.
    - Out-of-order events (e.g. `dispatch_started` before `restaurant_accepted`) are ignored, not queued.
    - `processed_event_ids` is a list, so the duplicate check is O(n) per event (see `optimizations.md`).

AI assistance: these fixes and this write-up were produced with an AI coding assistant, under permission granted by the evaluators. I reviewed every change and can explain it.