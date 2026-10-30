# TESTING.md — Required submission

## Test command and environment
- **Python version:** Python 3.13.15 (win32)
- **Command run:** `python -m pytest -v`
- **Actual test summary:** `220 passed in 0.42s` (100% passing, 0 failures, 0 skipped, 0 warnings)

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Duplicate event replay: replaying `event_id="EV-000"` (`payment_confirmed`) on an already paid order. | State must remain `PAID`, and `processed_event_ids` must not duplicate the ID (`["EV-000"]`). | `payment_status == "PAID"`, `processed_event_ids == ["EV-000"]` | `tests/test_acceptance_matrix.py::test_payment_event_replay_idempotent[EV-000]` |
| 2 | Boolean amount in refund: `amount_paise=True` on a cancelled order with 5000 paise due. | Boolean flag must not be treated as integer 1 paise; refund must be rejected and `refunded_paise` remains 0. | `refunded_paise == 0`, `payment_status == "PAID"` | `tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]` |
| 3 | Over-refund attempt: Initial partial refund of 4000 paise on 5000 due, followed by second refund of 2000 paise. | Second refund exceeds outstanding due balance (1000 paise) and must be ignored; total refund stays 4000 paise. | `refunded_paise == 4000`, `refunded_paise <= 5000` | `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due[4000-2000]` |
| 4 | Cancellation requested after dispatch: `cancel_requested` received when order is in `OUT_FOR_DELIVERY` status. | Order cancellation is prohibited once dispatched; status remains `OUT_FOR_DELIVERY`. | `status == "OUT_FOR_DELIVERY"` | `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` |
| 5 | Dual discrepancy reconciliation: Internal record `{"order_id": "A", "amount_paise": 1000, "status": "PLACED"}` vs provider `{"order_id": "A", "amount_paise": 800, "status": "CANCELLED"}`. | Order "A" must be reported in both `amount_mismatches` and `status_mismatches`, and omitted from `matched`. | `amount_mismatches == ["A"]`, `status_mismatches == ["A"]`, `matched == []` | `tests/test_contract.py::test_reconcile_both_amount_and_status_mismatch` |
| 6 | Late payment after rejection: Order rejected while `UNPAID`, then `payment_confirmed` arrives later. | Order remains `REJECTED`, `payment_status` updates to `PAID`, and `refund_due_paise` is populated with `total_paise` (1000). | `status == "REJECTED"`, `payment_status == "PAID"`, `refund_due_paise == 1000` | `tests/test_contract.py::test_late_payment_confirmed_on_rejected_order` |
| 7 | Multi-step refund reaching exact due: Order with 1000 due receives refund of 400, then 600. | First refund leaves status `PAID`; second refund completes full due amount and transitions `payment_status` to `REFUNDED`. | Step 1: `refunded_paise == 400, payment_status == "PAID"`; Step 2: `refunded_paise == 1000, payment_status == "REFUNDED"` | `tests/test_contract.py::test_two_step_partial_refund_to_full_refund` |

## Regression tests added
- `test_late_payment_confirmed_on_rejected_order`: Verifies that a payment confirmed after a restaurant rejection sets `refund_due_paise` to total paise.
- `test_late_payment_confirmed_on_cancelled_order`: Verifies that a payment confirmed after a cancellation sets `refund_due_paise` to total paise.
- `test_reconcile_both_amount_and_status_mismatch`: Verifies that orders with both amount and status discrepancies appear in both mismatch lists and not in matched.
- `test_reconcile_supports_total_paise_internal_orders`: Verifies that internal orders formatted with `total_paise` reconcile against provider `amount_paise`.
- `test_refund_boolean_type_ignored`: Verifies that boolean inputs (`True`/`False`) are not coerced to integers during refund processing.
- `test_two_step_partial_refund_to_full_refund`: Verifies that partial refunds preserve `PAID` until cumulative refund matches total due amount, then set `REFUNDED`.
- `test_replayed_refund_event_does_not_double_refund`: Verifies that duplicate refund events do not process duplicate monetary refunds.
- `test_malformed_event_and_order_inputs`: Verifies graceful defensive handling of `None` and non-dictionary inputs.

## Remaining failures or limitations
- None. All 220 tests in the test suite pass cleanly without failures or skips.
