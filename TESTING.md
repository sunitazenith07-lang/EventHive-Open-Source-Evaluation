# TESTING.md — Required submission

## Test command and environment
- **Python version:** `Python 3.13.15`
- **Command run:** `python -m pytest -q` (and `python -m pytest -v`)
- **Actual test summary:**
  - **Untouched baseline:** `62 failed, 150 passed, 2 warnings in 0.43s` (212 total tests)
  - **Final after fixes and regression tests:** `220 passed, 1 warning in 0.18s` (220 total tests, 0 failures)

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Duplicate `event_id` replay with identical or conflicting payload (`EV-DUP` with `500` paise then `200` paise) | Second event is ignored; `refunded_paise` remains `500` and `processed_event_ids` is `["EV-DUP"]` | `refunded_paise == 500`, `processed_event_ids == ["EV-DUP"]` (Passed) | `tests/test_contract.py::test_duplicate_event_with_conflicting_payload_is_ignored` & `test_payment_event_replay_idempotent` |
| 2 | Sequential partial refunds (`400` + `600` on `1000` due) followed by over-refund (`100`) | First keeps `PAID` (`400`), second flips to `REFUNDED` (`1000`), third is ignored (`1000`) | `o1["payment_status"] == "PAID"`, `o2["payment_status"] == "REFUNDED"`, `o3["refunded_paise"] == 1000` (Passed) | `tests/test_contract.py::test_sequential_partial_refunds_complete_on_exact_total_and_block_over_refund` |
| 3 | Late `payment_confirmed` arriving after order was already `REJECTED` or `CANCELLED` while `UNPAID` | `payment_status` becomes `PAID` and `refund_due_paise` is set to `total_paise` (`2500`), enabling subsequent refund | `paid_rej["payment_status"] == "PAID"`, `paid_rej["refund_due_paise"] == 2500`, subsequent refund succeeds (Passed) | `tests/test_contract.py::test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due` |
| 4 | Boolean (`True`, `False`), float (`100.0`), string (`"500"`), `None`, negative (`-10`), or zero (`0`) `amount_paise` in `refund_processed` | Invalid refund amounts are rejected completely; `refunded_paise` stays `0` and `payment_status` stays `PAID` | `refunded_paise == 0` and `payment_status == "PAID"` across all invalid inputs (Passed) | `tests/test_contract.py::test_boolean_and_non_integer_refund_amounts_rejected` & `test_invalid_refund_amounts_are_ignored` |
| 5 | Internal order (`total_paise=5000, status="ACCEPTED"`) vs Provider (`amount_paise=4500, status="CANCELLED"`) | Order ID is reported in both `amount_mismatches` and `status_mismatches`, and excluded from `matched` | `amount_mismatches == ["ORD-1"]`, `status_mismatches == ["ORD-1"]`, `matched == []` (Passed) | `tests/test_contract.py::test_reconcile_handles_total_paise_and_simultaneous_amount_and_status_mismatch` |
| 6 | Cancellation requested after dispatch (`status="OUT_FOR_DELIVERY"`) | Transition is blocked; order remains `OUT_FOR_DELIVERY` and `refund_due_paise` remains `0` | `out["status"] == "OUT_FOR_DELIVERY"` (Passed) | `tests/test_contract.py::test_cancel_after_dispatch_is_ignored` |
| 7 | Malformed inputs (`None`, non-dict orders/events, missing `event_id`, corrupted `processed_event_ids`) and full `data/records.json` replay | State is never corrupted, no unhandled exceptions occur, and `refunded_paise <= refund_due_paise` holds for all 150 orders | All assertions pass without error (Passed) | `tests/test_contract.py::test_malformed_and_missing_fields_do_not_corrupt_state` & `test_records_json_dataset_reconciliation_and_events_smoke` |

## Regression tests added
Added 8 new tests to `tests/test_contract.py`:
1. `test_duplicate_event_with_conflicting_payload_is_ignored` — prevents duplicate `event_id` replay from mutating state even if payload differs.
2. `test_sequential_partial_refunds_complete_on_exact_total_and_block_over_refund` — protects partial refund accumulation, `REFUNDED` status flip on full due amount, and over-refund blocking.
3. `test_late_payment_confirmed_after_rejection_or_cancellation_sets_refund_due` — ensures orders rejected/cancelled before payment confirmation properly record `refund_due_paise` when payment confirmation arrives late.
4. `test_boolean_and_non_integer_refund_amounts_rejected` — prevents `bool` (`True`/`False`), `float`, `str`, `None`, `list`, and `dict` values from being treated as valid paise amounts.
5. `test_reconcile_handles_total_paise_and_simultaneous_amount_and_status_mismatch` — verifies `total_paise` fallback and independent reporting of simultaneous amount and status mismatches.
6. `test_malformed_and_missing_fields_do_not_corrupt_state` — guards against `None`, non-dict inputs, and missing keys in `apply_order_event` and `reconcile_orders`.
7. `test_records_json_dataset_reconciliation_and_events_smoke` — validates reconciliation and event replay over all 150 internal orders, 163 provider records, and 219 events in `data/records.json`.
8. `test_summarize_orders_by_state` — verifies the optional stretch helper `summarize_orders_by_state`.

## Remaining failures or limitations
- **Remaining test failures:** `0` (`220 passed` out of 220 tests).
- **Known limitations:** Reconciliation keys records by `order_id`; if a single source list contains duplicate `order_id` dicts, the last record wins. Out-of-order delivery transitions (e.g., `order_delivered` arriving before `dispatch_started`) are safely ignored rather than queued for retry.
