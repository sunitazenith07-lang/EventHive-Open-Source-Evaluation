# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- **Python version:** Python 3.13.15
- **Command run:** `python -m pytest -q`
- **Actual test summary:** `222 passed in 1.06s` (212 existing starter tests + 10 regression and edge-case tests; 0 failed, 0 errors, 0 skipped).

---

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Order in `OUT_FOR_DELIVERY` receives `cancel_requested` | Status must remain `OUT_FOR_DELIVERY`; cancellation after dispatch is ignored; `refund_due_paise` remains 0. | `result["status"] == "OUT_FOR_DELIVERY"`, `refund_due_paise == 0`. | `tests/test_regression_and_edge_cases.py::test_cancel_after_dispatch_ignored` |
| 2 | Duplicate event replayed with different payload (`event_id="EV-1"` replayed as `restaurant_rejected` after payment confirmed) | Second event should be ignored because its `event_id` was already processed; state should not change. | `result["status"] == "PLACED"`, `result["processed_event_ids"] == ["EV-1"]`. | `tests/test_regression_and_edge_cases.py::test_duplicate_event_with_same_id_is_ignored` |
| 3 | Order cancelled first while unpaid, then late `payment_confirmed` webhook arrives | Order stays `CANCELLED`, payment status becomes `PAID`, and `refund_due_paise` is updated to full total amount (15000 paise). | `result["status"] == "CANCELLED"`, `result["payment_status"] == "PAID"`, `result["refund_due_paise"] == 15000`. | `tests/test_regression_and_edge_cases.py::test_late_payment_after_cancellation` |
| 4 | Non-integer refund amounts passed (`amount_paise=True`, `100.5`, `"500"`, `None`, `[]`) | Invalid amounts ignored; `refunded_paise` remains 0; status remains `PAID`. | `result["refunded_paise"] == 0`, `result["payment_status"] == "PAID"`. | `tests/test_regression_and_edge_cases.py::test_boolean_refund_amount_rejected` |
| 5 | Multi-step partial refunds and over-limit attempt (due 5000 paise) | Refund 2000 -> 2000 refunded, PAID. Over-limit 3500 attempt -> ignored. Remaining 3000 -> 5000 refunded, REFUNDED. Extra 1 paise -> ignored. | `result["refunded_paise"] == 5000`, `result["payment_status"] == "REFUNDED"`. | `tests/test_regression_and_edge_cases.py::test_partial_refunds_and_over_limit` |
| 6 | Order has both amount and status differences during reconciliation (Internal: 4000 paise / `ACCEPTED`; Provider: 3000 paise / `DELIVERED`) | Order ID must be included in both `amount_mismatches` and `status_mismatches`, and not in `matched`. | `report["amount_mismatches"] == ["ORD-BOTH"]`, `report["status_mismatches"] == ["ORD-BOTH"]`, `report["matched"] == []`. | `tests/test_regression_and_edge_cases.py::test_amount_and_status_mismatch_together` |
| 7 | Full integration with synthetic dataset `data/records.json` (150 internal orders, 163 provider records) | Report missing orders, amount mismatches, and status mismatches accurately. | matched=107, missing_prov=12, missing_int=25, amt_mismatch=20, status_mismatch=12, dual mismatch on ORD-1078. | `tests/test_regression_and_edge_cases.py::test_records_json_dataset` |

---

## Regression tests added
1. **Idempotency event replay:**
   - Fixed `processed_event_ids` appending duplicates and mutating order on replayed events.
   - Tests: `test_acceptance_matrix.py::test_payment_event_replay_idempotent`, `test_contract.py::test_duplicate_event_is_idempotent`, `test_regression_and_edge_cases.py::test_duplicate_event_with_same_id_is_ignored`.
2. **Refund eligibility and amount checks:**
   - Fixed unvalidated refund additions, boolean `True` being treated as `1`, and premature `REFUNDED` status on zero due orders.
   - Tests: `test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored`, `test_acceptance_matrix.py::test_refund_eligibility_matrix`, `test_acceptance_matrix.py::test_refunds_cannot_exceed_due`, `test_regression_and_edge_cases.py::test_boolean_refund_amount_rejected`, `test_regression_and_edge_cases.py::test_partial_refunds_and_over_limit`.
3. **Reconciliation status difference reporting:**
   - Fixed missing status checks in `reconcile_orders` and amount field lookup across differing schemas (`total_paise` vs `amount_paise`).
   - Tests: `test_acceptance_matrix.py::test_reconciliation_status_mismatch_matrix`, `test_contract.py::test_reconcile_reports_status_difference`, `test_regression_and_edge_cases.py::test_amount_and_status_mismatch_together`.
4. **Late payment on rejected/cancelled orders:**
   - Fixed refund due calculation when payment confirms after rejection or cancellation.
   - Test: `test_regression_and_edge_cases.py::test_late_payment_after_cancellation`.
5. **Awaiting-refund CSV export (stretch task):**
   - Added automated CSV export for orders with pending refundable balances.
   - Test: `test_regression_and_edge_cases.py::test_export_awaiting_refund_csv`.

---

## Remaining failures or limitations
- **Remaining failures:** None. All 222 tests pass green.
- **Known limitations:** Events are processed synchronously in-memory. For a production system with multiple concurrent workers, we would need database row-level locking or distributed locks (like Redis) on `order_id` to prevent race conditions.
