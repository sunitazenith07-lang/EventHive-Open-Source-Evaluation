# My Approach

## 1. Baseline

First thing I did was read the problem statement carefully to understand what the system was supposed to do. It's a food delivery order system — orders move through states like PLACED → ACCEPTED → OUT_FOR_DELIVERY → DELIVERED, and when something goes wrong the customer should get a refund.

Before touching any code, I ran the tests to see where things stood:

```
python -m pytest -v
```

Result: **62 failed, 150 passed** out of 212 total tests.

I also ran `python -m main` to see what the demo output looked like. It printed the reconciliation report — amounts and statuses compared between internal records and the payment provider. Nothing crashed, but the output was clearly wrong (status mismatches were being silently ignored).

---

## 2. Codebase Understanding

I read through these files in order:

- **models.py** — just one function, `new_order()`. It creates a fresh order dict with sensible defaults. Nothing wrong here.
- **fixtures.py** — sample data for the demo. Three orders, some provider records. Fine as-is.
- **main.py** — just calls `reconcile_orders()` and prints the result. Fine.
- **service.py** — this is where all the logic lives, and where all the bugs are.
- **tests/test_contract.py** and **tests/test_acceptance_matrix.py** — I read every test assertion before touching anything. This helped me understand what "correct" actually means.

The order lifecycle I traced:

```
PLACED
  → restaurant_accepted  → ACCEPTED
  → restaurant_rejected  → REJECTED  (refund due if paid)
  → cancel_requested     → CANCELLED (refund due if paid)

ACCEPTED
  → cancel_requested     → CANCELLED (refund due if paid)
  → dispatch_started     → OUT_FOR_DELIVERY

OUT_FOR_DELIVERY
  → order_delivered      → DELIVERED

CANCELLED or REJECTED
  → refund_processed     → updates refunded_paise, marks REFUNDED when fully done
```

I confirmed my understanding by tracing through specific test cases by hand — for example, `test_cancel_after_dispatch_is_ignored` made it clear that once an order is dispatched, cancellation requests must be silently ignored.

---

## 3. Investigation and Fixes

### Bug 1 — Duplicate events were being applied twice

**Symptom:** `test_duplicate_event_is_idempotent` failed. Sending the same event twice resulted in `["e1", "e1"]` in `processed_event_ids` instead of `["e1"]`.

**Root cause:** The code always appended `event_id` at the end and never checked if that ID had already been seen. So replaying an event would run all the logic a second time.

**Fix:** Added a check right at the start — if `event_id` is already in `processed_event_ids`, return the order unchanged immediately.

---

### Bug 2 — Refunds had no eligibility check

**Symptom:** `test_refund_requires_eligible_order` failed. A brand new PLACED, UNPAID order was getting its `refunded_paise` incremented when a `refund_processed` event came in.

**Root cause:** The `refund_processed` block had no guard at all. It just added money to `refunded_paise` for any order, regardless of status or whether the customer had even paid.

**Fix:** Added three checks before doing anything with the refund:
1. Order must be in `CANCELLED` or `REJECTED` state
2. `payment_status` must be `PAID`
3. `refund_due_paise` must be greater than zero

If any of these fail, I skip the refund entirely.

---

### Bug 3 — Refund amounts weren't being validated

**Symptom:** `test_refund_must_be_positive` and `test_invalid_refund_amounts_are_ignored` both failed. Zero, negative numbers, floats, strings, `None`, and even `True` were all being accepted as valid refund amounts.

**Root cause:** The code did `event.get("amount_paise", 0)` with zero checks on what that value actually was. In Python, `True` is a subclass of `int` and equals `1`, so `isinstance(True, int)` is `True` — meaning `True` would pass a naive int check.

**Fix:** Validate strictly — `amount` must be an `int`, must NOT be a `bool`, and must be strictly greater than zero. If any of those fail, skip the refund.

---

### Bug 4 — Refunds could exceed the total amount owed

**Symptom:** `test_refund_cannot_exceed_amount_due` and several parametrized cases in `test_refunds_cannot_exceed_due` failed. You could refund ₹3000 + ₹4000 on a ₹5000 order and end up with `refunded_paise = 7000`.

**Root cause:** There was no ceiling. The code just did `+= amount` with no check on how much had already been refunded or how much was still left to refund.

**Fix:** Calculate the remaining refundable amount (`refund_due_paise - refunded_paise`) and reject the event if the new amount would exceed it.

---

### Bug 5 — Status mismatches in reconciliation were silently ignored

**Symptom:** `test_reconcile_reports_status_difference` failed. When two records had matching amounts but different statuses (e.g. internal says "PLACED", provider says "DELIVERED"), the code was adding it to `matched` instead of `status_mismatches`.

**Root cause:** The `else` branch after the amount check just dumped everything into `matched` — it never looked at the `status` field at all. There's even a comment in the original code saying "Deliberate starter defect".

**Fix:** Added an `elif` between the amount check and the `matched` branch. If amounts match but statuses differ, put it in `status_mismatches`. Only if both match does it go into `matched`.

---

## 4. Implementation Decisions

**I only changed `service.py`.** No other file needed editing — the models, fixtures, tests and main script were all correct.

For the refund eligibility check, I considered putting it as part of the big `if/elif` chain. But I decided a separate early-return guard block was cleaner — it's easier to read and reason about each condition on its own line.

For idempotency, I placed the check right after setting defaults and reading `event_id`. This way it acts like a gate — nothing else even runs if the event was already processed.

One assumption I made: an event with `event_id = None` is treated like any other event ID. If `None` appears twice, the second one is a duplicate. This is consistent with how the rest of the code handles it.

I also chose to **reject** a refund that would exceed the due amount, rather than capping it. The test `test_refunds_cannot_exceed_due` confirms this — if the second refund would push the total over the limit, the whole event is dropped.

---

## 5. Verification

After my changes, I ran the full test suite:

```
python -m pytest -v
```

Result: **212 passed, 0 failed**

All 62 previously failing tests now pass. The 150 that were already passing still pass — I didn't break anything.

Key edge cases I verified by reading the tests:

- `True` as a refund amount → rejected (Bug 3)
- Partial refund does NOT set status to REFUNDED → correct
- Cancel after dispatch → order stays OUT_FOR_DELIVERY → correct
- Same event replayed 20 times → state changes only once → correct
- Both amount AND status must match for reconciliation to call it "matched" → correct

**Known limitations:**
- The service doesn't validate that `event_id` is a non-empty string — a `None` event_id works but might cause confusion if the caller doesn't set it.
- Events that aren't recognised (unknown type) still get their `event_id` recorded in `processed_event_ids`. This means replaying an unknown event is also idempotent, which seems fine.
- There's no ordering guarantee — if events arrive out of order, the state machine will simply ignore invalid transitions silently. That's by design per the problem statement.
