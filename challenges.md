# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour
Silent failures. Reconciliation put orders with the same amount but a different status in `matched` with no error. Separately, four of my new refund tests failed with no exception, because `apply_order_event()` ignores invalid refund events without any message.

## 2. Evidence
- Original suite: `62 failed, 150 passed`; `test_reconciliation_status_mismatch_matrix` exposed the reconciliation problem.
- After adding my first 6 tests:
  ```text
  >       assert order["refunded_paise"] == 400
  E       assert 0 == 400
  4 failed, 214 passed
  ```
  Only the four refund tests failed.

## 3. What I tried
1. Noticed `refunded_paise` stayed 0 in every failing test.
2. Read the `refund_processed` branch: it reads `event.get("amount_paise")`.
3. My test helper sent the amount under `"amount"`, so the service got `None` and ignored the event.
4. Changed the helper to `"amount_paise"` and re-ran the suite. All tests passed.
5. For reconciliation, read `reconcile_orders()`, saw only the amount was compared, and added a status check.

## 4. Resolution
- Root cause: wrong event key in my test helper (the service was working as designed); and in `reconcile_orders()`, a match was declared after comparing only the amount.
- What changed: the helper key; a status comparison in `reconcile_orders()`.
- Why it fixes the cause: refund events now carry the key the service reads, and an order is `matched` only if amount and status both match.

## 5. Proof and regression prevention
- Final full suite: 226 passed.
- Reconciliation tests: `test_reconciliation_status_mismatch_matrix` (existing) plus three new reconciliation tests.
- Cases that could still break: events with no `event_id`, an ignored refund that still records its event ID, and both amount and status differing.

## 6. Unresolved challenge or next step
Three behaviours are documented by tests but not changed, because the intended rule is unclear: (1) both amount and status differ, only the amount is reported; (2) events with no `event_id` after the first are treated as duplicates; (3) an invalid refund still marks its event ID processed. Next step: confirm the intended rule, write a failing test, then change `service.py`.