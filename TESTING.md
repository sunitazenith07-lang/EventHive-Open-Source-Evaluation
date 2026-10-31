# TESTING.md — Test Results & Edge-Case Evidence

## 1. Test Command and Environment
- **Python version:** `Python 3.15.2` (Darwin Kernel, macOS)
- **Pytest version:** `pytest-9.2.0`
- **Commands run:**
  - `python3 -m pytest -q`
  - `python3 -m pytest -v`
  - `python3 -m main`
- **Actual test summary:**
  - `221 passed in 0.09s`
  - 0 failed, 0 errors, 0 skipped.
  - 100% pass rate across baseline test matrix (212 tests) and new regression suites (9 tests).

---

## 2. Edge-Case Evidence

| # | Case / Input | Expected Behaviour | Actual Result | Test Name or Evidence |
|---|---|---|---|---|
| 1 | Replaying identical `event_id` ("EV-000") with `payment_confirmed` on order | Replayed event is ignored; `payment_status="PAID"`; `processed_event_ids` contains single ID without duplicates | Handled as idempotent no-op; `processed_event_ids=["EV-000"]` | `test_payment_event_replay_idempotent[EV-000]` & `test_duplicate_event_is_idempotent` |
| 2 | Invalid refund amounts: `True`, `0.5`, `-10`, `0`, `5001` (exceeding 5000 due) | All non-positive, non-integer, or excessive amounts ignored; `refunded_paise` stays 0; `payment_status="PAID"` | Values rejected without state mutation; `refunded_paise=0` | `test_invalid_refund_amounts_are_ignored` |
| 3 | Partial refund followed by final refund (e.g. 2500 then 2500 on 5000 due) | Partial maintains `payment_status="PAID"`; final transitions status to `"REFUNDED"` | After 2500: `PAID`; after 5000: `REFUNDED` | `test_valid_partial_and_full_refunds` & `test_multi_step_partial_refunds_and_overpayment_protection` |
| 4 | Cancellation request after order dispatch (`status="OUT_FOR_DELIVERY"`) | Cancellation is rejected; order remains in `OUT_FOR_DELIVERY` | Order stays `OUT_FOR_DELIVERY`; refund due stays 0 | `test_cancel_after_dispatch_is_ignored` & `test_cancellation_after_dispatch_is_safely_ignored` |
| 5 | Late `payment_confirmed` on order previously rejected while unpaid | `payment_status` becomes `"PAID"`; `refund_due_paise` set to `total_paise` (1000 paise) | `payment_status="PAID"`, `refund_due_paise=1000` | `test_late_payment_confirmed_after_rejection_or_cancellation` |
| 6 | Reconciliation record differing in both amount and status (`ORD-1078` in `records.json`) | Order ID reported in both `amount_mismatches` and `status_mismatches`; absent from `matched` | Present in both mismatch lists; absent from `matched` | `test_reconciliation_dual_mismatch_and_key_handling` & `test_full_dataset_reconciliation_from_records_json` |

---

## 3. Regression Tests Added
All regression tests are housed in `tests/test_regression.py` and run as part of the default `pytest` invocation:

1. **`test_duplicate_event_payload_conflict_is_ignored`:**
   Prevents regressions where a replayed event with an altered or conflicting payload could overwrite order state.
2. **`test_late_payment_confirmed_after_rejection_or_cancellation`:**
   Guarantees that asynchronous or out-of-order payment confirmations properly mark `refund_due_paise = total_paise` on cancelled/rejected orders.
3. **`test_payment_confirmed_does_not_revert_refunded_status`:**
   Ensures duplicate payment confirmations do not revert an order from `REFUNDED` back to `PAID`.
4. **`test_cancellation_after_dispatch_is_safely_ignored`:**
   Protects the invariant that orders in `OUT_FOR_DELIVERY` or `DELIVERED` status cannot be cancelled.
5. **`test_multi_step_partial_refunds_and_overpayment_protection`:**
   Verifies cumulative partial refund tracking and ensures an intermediate over-refunding attempt does not corrupt the running `refunded_paise` balance.
6. **`test_malformed_event_and_empty_inputs`:**
   Validates resilience against non-dictionary inputs, `None`, empty dictionaries, and events lacking `event_id`.
7. **`test_reconciliation_dual_mismatch_and_key_handling`:**
   Ensures multi-dimensional discrepancies (amount + status) are reported in both discrepancy categories.
8. **`test_full_dataset_reconciliation_from_records_json`:**
   Verifies end-to-end reconciliation across all 150 internal orders and 163 provider records in `data/records.json`.
9. **`test_export_awaiting_refund_csv_stretch`:**
   Verifies the optional stretch feature for exporting operational awaiting-refund CSV reports.

---

## 4. Remaining Failures or Limitations
- **Remaining test failures:** 0. All 221 tests pass without failure or warning.
- **Known limitations:**
  - Event processing is in-memory and single-threaded. For production multi-instance workloads, idempotency checks and balance tracking would require distributed locks (e.g., Redis) or transactional database constraints.
