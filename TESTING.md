# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: Python 3.15.1
- Command run: `python -m pytest -v` and `python -m main`
- Actual test summary: 221 passed in 0.79s (100% passing across all acceptance matrix, contract, and regression test suites)

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Event replayed with same `event_id` (`event_id="EV-001"`, `payment_confirmed`) | State unchanged, event ID processed exactly once without duplicates in `processed_event_ids` | `payment_status="PAID"`, `processed_event_ids=["EV-001"]` | `tests/test_acceptance_matrix.py::test_payment_event_replay_idempotent` |
| 2 | Boolean amount passed to refund (`amount_paise=True` or `False`) | Ignored completely since boolean is not a valid monetary paise amount | `refunded_paise=0`, `payment_status="PAID"` | `tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]` & `test_regression.py::test_boolean_refund_amount_rejected` |
| 3 | Refund exceeding outstanding refundable due (`due=5000`, `refunded=0`, `amount=6000` or second refund exceeding remaining balance) | Disallowed and rejected; order refunded amount remains unchanged | `refunded_paise` not increased beyond balance | `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due` & `test_regression.py::test_refund_rejected_when_exceeding_remaining_due_after_partial` |
| 4 | Cancellation attempted after order has been dispatched or delivered (`OUT_FOR_DELIVERY` or `DELIVERED`) | Cancellation event ignored; status preserved, no refund due generated | Status stays `OUT_FOR_DELIVERY` / `DELIVERED`, `refund_due_paise=0` | `tests/test_acceptance_matrix.py::test_order_state_transition_matrix` & `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` |
| 5 | Order with both status mismatch and amount mismatch in reconciliation (internal: 1000 paise / PLACED; provider: 2000 paise / DELIVERED) | Order reported in both `amount_mismatches` and `status_mismatches`, excluded from `matched` | `amount_mismatches=["ORD-MISMATCH"]`, `status_mismatches=["ORD-MISMATCH"]`, `matched=[]` | `tests/test_regression.py::test_reconcile_both_amount_and_status_mismatch` |

## Regression tests added
List the defects fixed and the tests added to prevent them from returning:
1. `test_event_without_id_does_not_pollute_processed_ids`: Verifies events without `event_id` (or `None`) do not append `None` into `processed_event_ids`.
2. `test_payment_confirmed_after_rejection_sets_refund_due`: Verifies late-arriving payment confirmation on a rejected order correctly sets `refund_due_paise`.
3. `test_payment_confirmed_after_cancellation_sets_refund_due`: Verifies late-arriving payment confirmation on a cancelled order correctly sets `refund_due_paise`.
4. `test_sequential_partial_refunds_transition_to_refunded_on_exact_match`: Validates incremental partial refunds transitioning `payment_status` to `REFUNDED` only when cumulative refunds equal full due.
5. `test_refund_rejected_when_exceeding_remaining_due_after_partial`: Confirms multi-step refund attempts that breach the remaining refundable quota are safely rejected.
6. `test_boolean_refund_amount_rejected`: Prevents `bool` values (`True`/`False`) from being treated as integers in Python.
7. `test_reconcile_both_amount_and_status_mismatch`: Ensures reconciliation flags both amount and status discrepancies simultaneously without misclassifying as matched.
8. `test_reconcile_handles_total_paise_and_amount_paise_keys`: Guarantees seamless compatibility when internal orders use `total_paise` and provider records use `amount_paise`.
9. `test_cancellation_after_dispatch_does_not_affect_state`: Protects post-dispatch states against invalid cancellation attempts.

## Remaining failures or limitations
- 0 failing tests. All 212 original suite tests and 9 new regression tests pass.
- Limitations: Offline simulation service operates on memory dictionaries; production deployment would require transactional datastore and distributed lock for high-concurrency event ingestion.
