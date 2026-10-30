# TESTING.md

## Test command and environment
- Python version: 3.13.18 (CI uses 3.11), pytest 9.1.1
- Commands run: `python -m pip install -r requirements-dev.txt`, `python -m pytest -q`, `python -m main`
- Baseline on the untouched starter: **62 failed, 150 passed** (212 tests)
- After the fix, original tests only: **212 passed**
- After the fix, with new regression tests: **241 passed** (212 original + 29 in `tests/test_regressions.py`)
- After the stretch item (out-of-order flagging): **258 passed in 0.15s** (212 original + 46 new)
- No existing test was deleted, skipped or edited.

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Same `refund_processed` id (600 paise) applied twice to a paid cancelled order with 1000 due | Counted once; id recorded once | Starter: refunded 1200, REFUNDED, ids `['r1','r1']`. Fixed: `duplicate_event`, refunded stays at the first amount | `test_replayed_refund_is_counted_once`, `test_payment_event_replay_idempotent` |
| 2 | Refund amounts `0, -1, 0.5, True, None, "10", [], {}, 5001` on 5000 due | Rejected, state unchanged | Fixed: `invalid_refund_amount` / `refund_exceeds_outstanding`, refunded stays 0. Starter accepted `True` as 1 paise | `test_invalid_refund_amounts_are_ignored` (15 cases), `test_refund_must_be_positive` |
| 3 | `cancel_requested` on an OUT_FOR_DELIVERY, paid order | Status unchanged, no refund due | `invalid_transition`, OUT_FOR_DELIVERY, due 0 | `test_cancel_after_dispatch_reports_invalid_transition` |
| 4 | Partial refund 300 then 700 on 1000 due, then 1 more | PAID after 300; REFUNDED at 1000; extra refund rejected | PAID → REFUNDED, then `refund_not_eligible`, refunded stays 1000 | `test_partial_then_final_refund_completes_and_further_refunds_are_rejected` |
| 5 | Refund on an unpaid PLACED order | Rejected | Starter: payment_status became REFUNDED. Fixed: unchanged, `UNPAID` | `test_refund_requires_eligible_order`, `test_refund_eligibility_matrix` |
| 6 | Event with no `event_id` / `None` / `""` / int | Rejected, nothing recorded | `missing_event_id`, `processed_event_ids == []` | `test_event_without_usable_id_changes_nothing` |
| 7 | Event that is not a dict, or `type` is a list | No crash, rejected | `malformed_event` / `unknown_event_type` | `test_non_dict_event_does_not_crash`, `test_unhashable_event_type_does_not_crash` |
| 8 | Same amount, different status (e.g. PLACED vs CANCELLED) | Reported as status mismatch, not matched | Starter: `matched`. Fixed: `status_mismatches` | `test_reconcile_reports_status_difference`, `test_reconciliation_status_mismatch_matrix` |
| 9 | Internal order from `new_order` (uses `total_paise`) vs provider row (uses `amount_paise`), same amount | Matched | Starter demo: `ORD-101` reported as amount mismatch (None vs 45900). Fixed: matched | `test_reconcile_reads_total_paise_from_internal_orders`, `python -m main` |
| 10 | Amount and status both differ | Reported in both lists | Both `amount_mismatches` and `status_mismatches` contain the id | `test_amount_and_status_mismatch_are_both_reported` |
| 11 | Reconciliation input with a row missing `order_id`, a `None` row, and a duplicated provider id | No crash; listed in `invalid_records` | 3 entries in input order; valid row still matched | `test_malformed_and_duplicate_records_are_reported_not_crashed_on` |
| 12 | Empty inputs to `reconcile_orders` and `process_events` | Empty report / empty state | All lists empty; `({}, [])` | `test_empty_reconciliation`, `test_process_events_handles_empty_input` |
| 13 | All 219 events in `data/records.json` | No crash; refunds never exceed due; replaying applied events changes nothing | 33 applied, 186 rejected with reasons; replay → only `duplicate_event`; 3rd pass == 2nd pass | `test_dataset_replay_of_applied_events_is_idempotent_and_refunds_stay_in_bounds` |
| 14 | Stretch: `dispatch_started` on a PLACED order; refund before the cancel; vs. cancel after dispatch | Early events flagged `out_of_order: True`; late/impossible ones `False` | Early ones flagged; cancel-after-dispatch, invalid amounts, duplicates and unknown types are not. `records.json`: 21 early events, including ORD-1007's refund | `test_lifecycle_event_before_its_step_is_flagged_early`, `test_late_or_impossible_transition_is_not_flagged`, `test_refund_before_cancellation_is_flagged_early`, `test_dataset_flags_ord_1007_early_refund` |

## Regression tests added
All in `tests/test_regressions.py`:

- **Duplicate events re-applied** → replayed refund, replay with conflicting payload, missing/invalid event id.
- **Refund accepted with no validation** → partial-then-final refund, refund with no valid order total, early refund then redelivery.
- **Transitions / malformed input** → cancel after dispatch with reason, non-dict event, unhashable type, event for a different order, unpaid rejection, late payment after cancel, second payment with a new id.
- **Reconciliation** → `total_paise` vs `amount_paise`, amount + status together, `payment_status` mismatch, malformed/duplicate records, input-order independence, dataset consistency.
- **Batch processing** → empty input, unknown/missing order id and duplicates, inputs not mutated.
- **Stretch: out-of-order flagging** (17 tests) → early lifecycle events, late/impossible transitions, refund before cancel, refund before late payment, invalid events not mis-flagged, dataset run.

The new tests import `evaluate_order_event` and `process_events`, which do not exist in the starter. Run against the starter, the file errors at collection. That is expected; the defects themselves are shown by the starter-behaviour column above, reproduced by running the original `service.py`.

## Remaining failures or limitations
- No failing tests.
- Re-running an entire event stream can change an order once, when an event arrived before the order was eligible (see ORDER_FLOW_NOTES.md, edge case 3). This is a deliberate trade-off and is tested.
- Event ids are de-duplicated per order, not globally.
