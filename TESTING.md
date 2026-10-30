# TESTING.md

## Test command and environment

- **Python version:** 3.14.7
- **Command run:** `python -m pytest -v`
- **Actual test summary:** 212 passed, 0 failed

---

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name |
|---|---|---|---|---|
| 1 | Send the same event twice (same `event_id`) | Order should only change once. Second time does nothing. |  Works correctly — `processed_event_ids` has the ID only once | `test_duplicate_event_is_idempotent` |
| 2 | Send `cancel_requested` after order is already dispatched (`OUT_FOR_DELIVERY`) | Cancel should be ignored. Order stays as `OUT_FOR_DELIVERY`. |  Works correctly — status did not change | `test_cancel_after_dispatch_is_ignored` |
| 3 | Send `refund_processed` on a delivered order (not cancelled/rejected) | Refund should be ignored. `refunded_paise` stays 0. |  Works correctly — no refund applied | `test_refund_requires_eligible_order` |
| 4 | Send a refund with `amount_paise = True` | Should be rejected. `True` is not a valid number. |  Works correctly — refund ignored | `test_invalid_refund_amounts_are_ignored[True]` |
| 5 | Send two refunds that together add up to more than the order total | Second refund should be rejected. Total refunded must not go over the due amount. |  Works correctly — second refund blocked | `test_refunds_cannot_exceed_due` |
| 6 | Send `refund_processed` with `amount_paise = 0` | Zero is not a valid refund. Should be ignored. |  Works correctly — refund ignored | `test_refund_must_be_positive` |
| 7 | Reconcile two records with same amount but different status (one says PLACED, other says DELIVERED) | Should go into `status_mismatches`, not `matched` |  Works correctly — reported as status mismatch | `test_reconcile_reports_status_difference` |
| 8 | Send `restaurant_accepted` when order is already `ACCEPTED` | Should do nothing — can't accept twice |  Works correctly — status stays ACCEPTED | `test_order_state_transition_matrix[ACCEPTED-restaurant_accepted-ACCEPTED]` |
| 9 | Partial refund — refund only half the amount owed | `payment_status` should stay `PAID`, not flip to `REFUNDED` |  Works correctly — stays PAID until fully refunded | `test_partial_refund_is_not_marked_complete` |
| 10 | Send an unknown event type like `"chargeback"` or `"cancel"` | Order should not change at all |  Works correctly — state untouched | `test_unknown_event_does_not_mutate_order_state` |

---

## Regression tests added

These are the bugs that were fixed. The tests already existed in the starter — they were failing before and now pass.

| Bug fixed | What was wrong | Test that covers it |
|---|---|---|
| No idempotency check | Same event applied twice, event_id appeared twice in the list | `test_duplicate_event_is_idempotent`, `test_payment_event_replay_idempotent` |
| No eligibility check on refunds | Any order (even delivered ones) could get refunded | `test_refund_requires_eligible_order`, `test_refund_eligibility_matrix` |
| No amount validation | Zero, negative, `True`, strings, floats — all accepted as refund amounts | `test_refund_must_be_positive`, `test_invalid_refund_amounts_are_ignored` |
| No cap on total refunded | Two refunds could add up to more than the order total | `test_refund_cannot_exceed_amount_due`, `test_refunds_cannot_exceed_due` |
| Reconcile missed status mismatches | Different statuses were being called "matched" | `test_reconcile_reports_status_difference`, `test_reconciliation_status_mismatch_matrix` |

---

## Remaining failures or limitations

**No tests are currently failing.** All 212 pass.

Known limitations I noticed but didn't fix (no tests require it):

- If `event_id` is `None`, the code still stores it and treats a second `None` event as a duplicate. It works, but it's a bit odd. A proper fix would reject events that have no valid ID.
- Events that arrive out of order are silently ignored — there's no warning. For example, if `dispatch_started` comes before `restaurant_accepted`, it just does nothing. The system is safe, but there's no log or error to help you debug it.
- The input validation only lives inside `apply_order_event`. If someone passes a completely broken order dict (missing `order_id`, or `total_paise` as a string), the code might behave unexpectedly. Not a problem for the current tests, but something to think about for a real system.
