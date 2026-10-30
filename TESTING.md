# TESTING.md — Required submission

## Test command and environment
- **Python version:** Python 3.14.7
- **Command run:** `python -m pytest -q`
- **Actual test summary:** `230 passed in 0.08s` (212 starter tests + 18 regression tests in `tests/test_regression.py`).

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Duplicate `payment_confirmed` event with same `event_id` | Ignored on second call; `processed_event_ids` has ID once | `processed_event_ids == ['EV-000']`, `payment_status == 'PAID'` | `test_payment_event_replay_idempotent` |
| 2 | Invalid refund amounts (`0`, `-10`, `0.5`, `True`, `None`, `"10"`) | Ignored; `refunded_paise` stays `0` | `refunded_paise == 0`, `payment_status == 'PAID'` | `test_invalid_refund_amounts_are_ignored` |
| 3 | Refund on ineligible order (e.g. `PLACED` or `UNPAID`) | Ignored; `refunded_paise` stays `0` | `refunded_paise == 0` | `test_refund_eligibility_matrix` |
| 4 | Two partial refunds where second exceeds remaining due (`4000` then `2000` on `5000` due) | First succeeds (`4000`), second is ignored | `refunded_paise == 4000`, `payment_status == 'PAID'` | `test_refunds_cannot_exceed_due` |
| 5 | `cancel_requested` after order is `OUT_FOR_DELIVERY` | Ignored; order stays `OUT_FOR_DELIVERY` | `status == 'OUT_FOR_DELIVERY'`, `refund_due_paise == 0` | `test_cancel_after_dispatch_is_safely_ignored` |
| 6 | Late `payment_confirmed` after unpaid order was `REJECTED` | Sets `payment_status = 'PAID'` and `refund_due_paise = total_paise` | `payment_status == 'PAID'`, `refund_due_paise == 4200` | `test_late_payment_confirmed_on_rejected_order_sets_refund_due` |

## Regression tests added
Added `tests/test_regression.py` to test:
- Duplicate event replay on payments and refunds (`test_idempotent_event_replay_preserves_event_list`, `test_idempotent_refund_replay_does_not_duplicate_refund`).
- Rejecting non-int/boolean/negative refund amounts (`test_refund_rejects_non_positive_or_non_integer`).
- Partial refunds adding up to the exact total (`test_refund_exact_split_to_full`).
- Late payment confirmation on a rejected order (`test_late_payment_confirmed_on_rejected_order_sets_refund_due`).
- Reconciling `total_paise` vs `amount_paise` and simultaneous status + amount mismatches (`test_reconcile_orders_supports_both_key_conventions`, `test_reconcile_orders_handles_simultaneous_amount_and_status_mismatch`).

## Remaining failures or limitations
- No failing tests remain (`230 passed`).
