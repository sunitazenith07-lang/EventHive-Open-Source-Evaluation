# TESTING.md — Required Submission

## Test command and environment
- **Python version:** Python 3.14.7
- **Command run:** `python -m pytest -q`
- **Actual test summary:** `222 passed in 0.45s` (all 212 existing acceptance/contract tests + 10 regression/edge-case tests passing with 0 failures).

---

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | **Duplicate event replay idempotency:** Event `{"event_id": "EV-001", "type": "payment_confirmed"}` replayed against paid order. | State must not mutate on second pass; `processed_event_ids` must not contain duplicate ID. | `payment_status == 'PAID'`, `processed_event_ids == ['EV-001']`. | `tests/test_acceptance_matrix.py::test_payment_event_replay_idempotent[EV-001]` |
| 2 | **Boolean amount type trap:** `refund_processed` event with `amount_paise=True` on cancelled paid order with 5000 paise due. | Python booleans (`True`/`False`) must be rejected despite `issubclass(bool, int)`; refund amount remains 0. | `refunded_paise == 0`, `payment_status == 'PAID'`. | `tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]` and `tests/test_regression_and_edge_cases.py::test_boolean_refund_amounts_are_rejected` |
| 3 | **Cancellation post-dispatch:** `cancel_requested` event arrives after order has reached `OUT_FOR_DELIVERY` or `DELIVERED`. | Order cancellation cannot be honored after dispatch; status remains unchanged, no refund due is assigned. | `status == 'OUT_FOR_DELIVERY'`, `refund_due_paise == 0`. | `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` and `tests/test_acceptance_matrix.py::test_order_state_transition_matrix[OUT_FOR_DELIVERY-cancel_requested-OUT_FOR_DELIVERY]` |
| 4 | **Cumulative refund exceeding due amount:** First refund of 4000 paise applied, followed by second refund of 2000 paise (due is 5000 paise). | Second refund exceeds outstanding due (1000 paise); it is rejected, cumulative refunded stays at 4000 paise. | `refunded_paise == 4000`, `payment_status == 'PAID'`. | `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due[4000-2000]` |
| 5 | **Simultaneous amount and status mismatch in reconciliation:** Internal `total_paise=2000`, `status=DELIVERED` vs Provider `amount_paise=1500`, `status=PLACED`. | Order is reported in BOTH `amount_mismatches` and `status_mismatches`; excluded from `matched`. | `report["amount_mismatches"] == ["ORD-10"]`, `report["status_mismatches"] == ["ORD-10"]`, `report["matched"] == []`. | `tests/test_regression_and_edge_cases.py::test_reconciliation_simultaneous_amount_and_status_mismatch` and verified on `ORD-1078` in `data/records.json` |
| 6 | **Late payment confirmation on rejected order:** Order rejected while UNPAID, followed by late `payment_confirmed`. | Status remains `REJECTED`, `payment_status` becomes `PAID`, `refund_due_paise` is initialized to order total. | `status == 'REJECTED'`, `payment_status == 'PAID'`, `refund_due_paise == 3000`. | `tests/test_regression_and_edge_cases.py::test_late_payment_confirmed_on_rejected_order_sets_refund_due` |

---

## Regression tests added
The following defects were resolved and safeguarded by new tests in `tests/test_regression_and_edge_cases.py`:

1. **Duplicate Cancellation Replay:**
   - *Defect:* Only payment events were explicitly checked for replay in starter tests; duplicate cancellation events could append redundant event IDs.
   - *Test Added:* `test_duplicate_cancellation_event_is_idempotent`.
2. **Asynchronous Late Payment on Rejected/Cancelled Orders:**
   - *Defect:* Orders rejected or cancelled before payment confirmation did not initialize `refund_due_paise` when payment subsequently cleared.
   - *Tests Added:* `test_late_payment_confirmed_on_rejected_order_sets_refund_due` and `test_late_payment_confirmed_on_cancelled_order_sets_refund_due`.
3. **Cancellation Post-Delivery:**
   - *Defect:* Verifies terminal delivery states strictly ignore customer cancellation attempts.
   - *Test Added:* `test_cancel_after_delivery_is_rejected`.
4. **Boundary Refund Protection:**
   - *Defect:* Ensures an overage of even 1 paise beyond outstanding refundable balance is strictly rejected, while exact remaining balance is accepted and completes the refund.
   - *Test Added:* `test_refund_exceeding_remaining_due_is_rejected`.
5. **Python Boolean Amount Rejection:**
   - *Defect:* Protects against Python's integer-boolean polymorphism.
   - *Test Added:* `test_boolean_refund_amounts_are_rejected`.
6. **Malformed Input Hardening:**
   - *Defect:* Non-dict inputs or events without `event_id` caused unhandled errors or appended `None` into event tracking.
   - *Test Added:* `test_malformed_inputs_handled_safely`.
7. **Simultaneous Amount and Status Mismatch Classification:**
   - *Defect:* Reconciler previously dropped status mismatches and failed when both dimensions differed.
   - *Test Added:* `test_reconciliation_simultaneous_amount_and_status_mismatch`.
8. **Malformed Reconciliation Record Resilience:**
   - *Defect:* Unhandled missing `order_id` in provider or internal list.
   - *Test Added:* `test_reconciliation_handles_malformed_records`.
9. **Operational Lifecycle Summary (Stretch Feature):**
   - *Defect:* Validates aggregation of order lifecycle states for operational reporting.
   - *Test Added:* `test_summarize_orders_by_state`.

---

## Remaining failures or limitations
- **Remaining Failures:** None. All 222 automated tests pass cleanly (`222 passed in 0.45s`).
- **Known Limitations:**
  - `processed_event_ids` is stored as an in-memory list; in production environments with massive transaction histories, event deduplication should be offloaded to a transactional database uniqueness constraint or Redis key with TTL.
  - Multi-currency operations are not modeled; all values are assumed to be in non-negative integer Indian paise.
