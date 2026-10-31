# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: Python 3.15.1
- Command run: `python -m pytest -q` and `python -m main`
- Actual test summary: 221 passed in 0.59s

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Duplicate event replay (`event_id="EV-001"`, `payment_confirmed`) | State does not change, event ID is not added twice | `payment_status="PAID"`, `processed_event_ids=["EV-001"]` | `tests/test_acceptance_matrix.py::test_payment_event_replay_idempotent` |
| 2 | Boolean amount passed to refund (`amount_paise=True`) | Rejected because boolean is not a valid amount | `refunded_paise=0`, `payment_status="PAID"` | `tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]` |
| 3 | Refund bigger than balance due (`due=5000`, `refunded=3000`, new amount `2500`) | Rejected, refunded amount stays 3000 | `refunded_paise=3000`, `payment_status="PAID"` | `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due` |
| 4 | Cancel after dispatch (`OUT_FOR_DELIVERY`) | Ignored, status stays `OUT_FOR_DELIVERY`, no refund due | Status stays `OUT_FOR_DELIVERY`, `refund_due_paise=0` | `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` |
| 5 | Order with both amount and status mismatch | Added to both `amount_mismatches` and `status_mismatches`, not in `matched` | `amount_mismatches=["ORD-MISMATCH"]`, `status_mismatches=["ORD-MISMATCH"]`, `matched=[]` | `tests/test_regression.py::test_reconcile_both_amount_and_status_mismatch` |

## Regression tests added
Tests added in `tests/test_regression.py`:
1. `test_event_without_id_does_not_pollute_processed_ids`: Events without `event_id` don't add `None` to `processed_event_ids`.
2. `test_payment_confirmed_after_rejection_sets_refund_due`: Late payment on rejected order sets `refund_due_paise`.
3. `test_payment_confirmed_after_cancellation_sets_refund_due`: Late payment on cancelled order sets `refund_due_paise`.
4. `test_sequential_partial_refunds_transition_to_refunded_on_exact_match`: Multiple partial refunds change status to `REFUNDED` only when 100% is paid.
5. `test_refund_rejected_when_exceeding_remaining_due_after_partial`: Partial refund + second refund exceeding total is rejected.
6. `test_boolean_refund_amount_rejected`: `True` and `False` are rejected as amounts.
7. `test_reconcile_both_amount_and_status_mismatch`: Reconcile reports both mismatches on the same order.
8. `test_reconcile_handles_total_paise_and_amount_paise_keys`: Reconcile works with both key names.
9. `test_cancellation_after_dispatch_does_not_affect_state`: Cancel after dispatch is ignored.

## Remaining failures or limitations
- 0 failures. All 221 tests pass.
