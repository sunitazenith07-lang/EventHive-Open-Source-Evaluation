# challenges.md

## 1. Challenge or confusing behaviour
Two things were hard.

1. **62 failures looked like 62 bugs.** I had to work out that they come from only three root causes (no duplicate check, an unvalidated refund branch, status never compared in reconciliation).
2. **What an ignored event should do to `processed_event_ids`.** The brief says refund notifications can arrive late or more than once. If every event with a usable id is recorded, a refund that is ignored once can never be applied later under the same id. If ids are recorded only when applied, replays of ignored events get re-evaluated. No visible test settles this, so it was a design decision.

## 2. Evidence
- Starter failures grouped by test name: 21 idempotency, 33 refund, 8 reconciliation (total 62).
- Starter demo output: ORD-101 and ORD-102 reported as amount mismatches with identical amounts, `status_mismatches` empty.
- The late-notification case with the final code (order `ORD-204`, total 5000):
  ```
  payment_confirmed p1                       -> PLACED PAID refund_due=0 refunded=0
  refund_processed  r1 amount_paise=5000     -> PLACED PAID refund_due=0 refunded=0, ids ['p1', 'r1']
  ```
  The refund arrived before the order was cancelled, was ignored, and id `r1` is now spent.
  n the starter, a refund amount of None or "500" crashed with TypeError: unsupported operand type(s) for +=: 'int' and 'NoneType' (and 'int' and 'str'). True was counted as 1 paise and 5.0 was accepted.
  reconcile_orders(None, None) raised TypeError: 'NoneType' object is not iterable. A row with a list as order_id raised TypeError: cannot use 'list' as a dict key, and a None row raised AttributeError: 'NoneType' object has no attribute 'get'.

## 3. What I tried
- Ran the suite and grouped the failures by test name; checked that 21 + 33 + 8 = 62.
- Ran `python -m pytest -q -k "idempotent"`, `-k "refund"` and `-k "reconcil"` to isolate each group, before and after the fix.
- Replayed one `payment_confirmed` event twice in a Python shell and saw the id list grow to `['e1', 'e1']`, which showed the list is written but never read.
- Checked `isinstance(True, int)` in Python (it is `True`), which explained why `True` was accepted as a refund of 1 paise.
- Ran `python -m main` on the starter and again after the fix, and compared the two outputs.
- Stashed my `service.py` change, ran the original tests and the demo on the starter, then restored it, to confirm the "before" numbers.
- Wrote edge-case tests and ran them against the starter to see which ones fail there.

## 4. Resolution
- Root cause 1: `apply_order_event` never checked `processed_event_ids` before changing state. Fix: a guard before the transition chain.
- Root cause 2: the `refund_processed` branch added the amount without checking order state, amount type, or the outstanding balance, and used `>=` to decide completion. Fix: gates for eligibility, amount validity and the outstanding cap, and `==` for completion.
- Root cause 3: `reconcile_orders` only compared amounts, in an `if/else` that left no room for a status check. Fix: two independent checks; `matched` needs both to agree.
- These address the causes, not the symptoms: no test output is hard-coded, and the rules are enforced for any input, not only the fixtures.
- For the recording question I chose "record every event with a usable id once seen". It is the smallest change and matches the starter's behaviour, and I accepted the cost described in section 6.

## 5. Proof and regression prevention
- The original 62 failing tests now pass (212 passed before I added tests, 246 with them).
- `tests/test_regressions.py` covers the replayed refund, unusable ids, non-integer amounts, a refund after a full refund, late payment after a refund, payment after cancellation, reconciliation with both fields wrong, mixed-type ids, rows with no id, and `None` inputs.
- `test_rejected_refund_id_is_still_recorded_so_it_cannot_be_retried` documents the recording decision, so changing the policy later will be a visible, deliberate change.
- Related cases that could still break: a new event type that changes status but forgets `_mark_refund_due`, and anyone changing the sort key in `reconcile_orders` (the mixed-id test guards that).

## 6. Unresolved challenge or next step
- A refund notification that arrives before the cancellation is ignored and its id is spent, so it cannot be retried with the same id. Next step: park such refunds as pending, or record an id only when the event was applied, and validate with a test that sends the refund first.
- Reconciliation silently skips rows without a usable `order_id` and keeps only the last of duplicate ids. Reporting them would need new keys in the report, which could break callers, so I left it and documented it.
- `apply_order_event` assumes `order` is a dict.