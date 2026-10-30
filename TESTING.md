# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- **Python version**: Python 3.14.4 (Windows 64-bit)
- **Command run**: `python -m pytest` / `python -m pytest -q`
- **Actual test summary**: `221 passed in 0.72s` on the latest recorded full-suite run (100% passing)

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Duplicate refund event replayed (`event_id="r1"`, `amount_paise=400`) on a paid, cancelled order | Second invocation ignored; `refunded_paise` remains 400; `event_id` not duplicated | `refunded_paise=400`, `processed_event_ids=['r1']` | `test_duplicate_refund_event_is_idempotent` |
| 2 | Cancellation requested after dispatch (`status="OUT_FOR_DELIVERY"`, event `cancel_requested`) | Order status remains unchanged (`OUT_FOR_DELIVERY`); no refund due assigned | `status="OUT_FOR_DELIVERY"`, `refund_due_paise=0` | `test_cancel_after_dispatch_is_ignored` |
| 3 | Invalid refund amounts (`0`, `-10`, `0.5`, `True`, `"10"`, `None`, exceeding due balance) | Event ignored; order state and `refunded_paise` remain unmodified | `refunded_paise=0`, `payment_status="PAID"` | `test_invalid_refund_amounts_are_ignored` |
| 4 | Order with simultaneous amount mismatch and status mismatch between internal and provider | Reported independently under both `amount_mismatches` and `status_mismatches`; excluded from `matched` | `amount_mismatches=['A']`, `status_mismatches=['A']`, `matched=[]` | `test_reconcile_reports_amount_and_status_differences_separately` |
| 5 | Late payment confirmation after order cancellation (`cancel_requested` before `payment_confirmed`) | Status remains `CANCELLED`; `payment_status` becomes `PAID`; `refund_due_paise` updated to `total_paise` | `status="CANCELLED"`, `payment_status="PAID"`, `refund_due_paise=1500` | `test_payment_confirmed_after_cancellation_marks_refund_due` |
| 6 | Consecutive partial refunds totaling exact due amount (`due=1000`, `r1=400`, `r2=600`) | First refund leaves status `PAID`; second refund transitions status to `REFUNDED` | `refunded_paise=1000`, `payment_status="REFUNDED"` | `test_paid_rejection_partial_then_full_refund_flow` |
| 7 | Malformed event input (empty dict, non-string `type`, missing `event_id`) | Safely ignored without raising exceptions or mutating order state | Exact order dictionary returned unmodified | `test_malformed_event_is_ignored` |

## Regression tests added
- `tests/test_contract.py::test_duplicate_refund_event_is_idempotent`:
  Prevents duplicate refund events with identical `event_id` from incrementing `refunded_paise` multiple times.
- `tests/test_contract.py::test_reconcile_reports_amount_and_status_differences_separately`:
  Guarantees that an order with both amount and status discrepancies is recorded in both mismatch lists.
- `tests/test_contract.py::test_payment_confirmed_after_cancellation_marks_refund_due`:
  Ensures that when asynchronous payment webhooks arrive after cancellation, `refund_due_paise` is accurately allocated.
- `tests/test_contract.py::test_payment_confirmed_after_rejection_marks_refund_due`:
  Ensures that when payment arrives after restaurant rejection, full refund due balance is established.
- `tests/test_acceptance_matrix.py::test_malformed_event_is_ignored`:
  Validates that empty dictionaries, missing event IDs, or non-string event types are safely ignored without raising exceptions.
- `tests/test_acceptance_matrix.py::test_unknown_event_does_not_mutate_order_state`:
  Verifies that unknown event kinds leave the order object completely unaltered.

## Remaining failures or limitations
- None. All 221 tests in `tests/test_contract.py` and `tests/test_acceptance_matrix.py` pass without errors or warnings.
