# approach.md

## 1. Baseline
- Commands run before editing: `python -m pip install -r requirements-dev.txt`, `python -m pytest -q`, `python -m main`.
- Initial test result: **62 failed, 150 passed** (212 tests, Python 3.13.18).
- Demo output observed: `matched: []`, `amount_mismatches: ['ORD-101', 'ORD-102']`, `status_mismatches: []`. ORD-101 has the same amount on both sides (45900), so this is already wrong.

## 2. Codebase understanding
- Files inspected: `service.py` (all logic), `models.py` (`new_order` shape), `fixtures.py`, `main.py`, both test files, `data/records.json` + `data/README.txt`, `.github/workflows/tests.yml`, `pyproject.toml`.
- Flow: `apply_order_event(order, event)` deep-copies the order, then branches on `event["type"]`. `reconcile_orders(internal, provider)` keys both lists by `order_id` and buckets each id.
- How understanding was confirmed:
  - Grouped the 62 failures by test function: refund validation, eligibility, over-refund, status mismatch and duplicates.
  - Reproduced each defect directly against the original `service.py`, e.g. replaying a 600-paise refund twice gave `refunded_paise = 1200` and REFUNDED on a 1000 due.
  - Profiled `records.json`. Internal orders carry `total_paise`; provider rows carry `amount_paise`. 7 events have no `event_id`, 7 have no `order_id`, and refund amounts include `None`, `True`, `1.5`, `"100"`, `0` and `-1`.

## 3. Investigation and implementation strategy
- **Issue 1: duplicates re-applied.** Symptom: `processed_event_ids == ['e1','e1']` after a replay. Cause: the starter appends the id but never checks it. Fix: return early with `duplicate_event` if the id is already processed. Events with no usable string id are rejected, since they cannot be de-duplicated.
- **Issue 2: refunds not validated.** Symptom: negative, zero, `True`, over-limit and ineligible refunds all changed state, and `refunded >= due` with `due = 0` marked unpaid orders REFUNDED. Cause: the refund branch only did `+=` and `>=`. Fix:
  - require a positive `int` that is not `bool`;
  - require status CANCELLED/REJECTED, payment PAID and an outstanding amount > 0;
  - reject anything above `due − refunded`;
  - mark REFUNDED only on `==`.
- **Issue 3: transitions.** The starter already guarded most statuses. Two gaps remained: `payment_confirmed` was unconditional, and an unknown `type` still recorded its id. The rules now live in one `TRANSITIONS` table, and every rejection returns a reason.
- **Issue 4: reconciliation.** Status was never compared (the `else` put every same-amount row in `matched`). Also, `elif` meant an amount mismatch hid a status mismatch. Fix: check amount, status and (when both sides have it) `payment_status` independently. `matched` is only for rows with no difference.
- **Issue 5: demo amount bug.** Internal records use `total_paise`, so every internal row compared `None` with the provider amount. Fix: `_amount()` reads `amount_paise`, falling back to `total_paise`.

## 4. Implementation decisions
- **Main change:** added `evaluate_order_event()`, which returns `(order, outcome)`. `apply_order_event()` is a thin wrapper that keeps the tested signature. `process_events()` applies a batch and returns a rejection list with index and reason, which covers unknown or missing order ids.
- **Rejected events are not recorded in `processed_event_ids`.** The alternative was to record every well-formed id. That gives strict "same stream twice = same state", but an early refund notification would be lost forever. Losing a real provider refund seemed worse.
- **Over-refunds are rejected whole, not capped.** Capping would hide a disagreement that reconciliation should surface.
- **No order is created from an event** for an unknown id; it is reported instead.
- **Assumptions:**
  - acceptance does not require payment (the starter matrix accepts an UNPAID order);
  - a late payment on a cancelled/rejected order creates a full refund due;
  - malformed or duplicated reconciliation rows go to a new `invalid_records` list instead of silently overwriting each other.

## 4b. Stretch item: flag out-of-order events
Chosen because it follows directly from the ORD-1007 case (see challenges.md).
- `is_out_of_order(order, event, outcome)` decides whether a rejection happened only because the event arrived *early*. The order has not reached the step the event needs, but still can.
- Early means: `dispatch_started` on PLACED; `order_delivered` on PLACED/ACCEPTED; a refund on PLACED/ACCEPTED (before the cancel/reject); or a refund on an UNPAID cancelled/rejected order (before the late payment).
- *Late* or impossible events are not flagged, because they can never become valid. Examples: cancel after dispatch, anything on DELIVERED.
- Invalid amounts, unknown types and missing ids are errors, not timing problems, so they are not flagged either.
- `process_events` adds an `out_of_order` flag to every rejection, and `out_of_order_events()` returns only the flagged ones. Events are flagged, not reordered or retried.

## 5. Verification
- **Tests added:** 46 in `tests/test_regressions.py` (29 for the fixes, 17 for the stretch item). No existing test changed.
- **Results:** 212/212 original tests pass, and **241 passed** with the fix tests, **258 passed** after the stretch item. `python -m main` now shows ORD-101 matched and ORD-102 as a status mismatch (ACCEPTED vs CANCELLED). The `records.json` run: 219 events, 33 applied, 186 rejected with reasons; 21 of the rejections are flagged out-of-order.
- **Edge cases verified:** see TESTING.md (13 rows) and ORDER_FLOW_NOTES.md.
- **Known limitations:**
  - event ids are per order, not global;
  - re-running a whole stream can apply an early event once (see challenges.md);
  - refunds after delivery are not modelled.
