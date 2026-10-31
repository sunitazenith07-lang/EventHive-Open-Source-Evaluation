# TESTING.md — Test Evidence

## Test command and environment

- **Test framework:** pytest
- **Command:** `python -m pytest -q`
- **Latest recorded full-suite result:** `219 passed in 0.69s`
- **Additional verification:** `git diff --check` produced no output (no whitespace errors).
- **Demo:** `python -m main` was run during integration verification.

## Edge-case evidence

| # | Case / input | Expected behaviour | Test or implementation evidence |
|---|---|---|---|
| 1 | The same event ID is received more than once. | A previously processed event is not applied again. | Existing idempotency coverage in `tests/test_acceptance_matrix.py` and `tests/test_contract.py`. |
| 2 | An event has an unsupported type. | The order is returned unchanged. | Event-type allow-list in `apply_order_event()`; acceptance-matrix coverage. |
| 3 | An event ID is empty, whitespace-only, or not a string. | The event is ignored. | Event-ID validation in `apply_order_event()`. |
| 4 | A non-refund event has no event ID. | It can be processed independently; `None` is not added to the processed-ID list or used to deduplicate other missing-ID events. | `test_events_without_event_id_are_processed_independently`. |
| 5 | A refund event has no event ID. | The refund is ignored because it cannot be reliably protected against replay. | `test_refund_without_event_id_is_ignored`. |
| 6 | A refund amount is zero, negative, non-integer, or greater than the outstanding amount. | The refund is ignored and the refunded total is not increased. | Existing refund validation tests in the acceptance matrix and contract suite. |
| 7 | A valid refund is processed partially and then fully. | Partial refunds keep payment status as `PAID`; status becomes `REFUNDED` only when the full due amount is refunded. | Existing partial/full refund tests. |
| 8 | A payment confirmation arrives when payment is already not `UNPAID`. | It does not overwrite the existing payment status. | Guard in `apply_order_event()`. |
| 9 | Internal `total_paise` and provider `amount_paise` contain the same value. | The records are not reported as an amount mismatch. | `test_reconcile_internal_total_against_provider_amount`. |
| 10 | The preferred amount field exists but is `None`. | Reconciliation falls back to the alternate amount field. | `test_reconcile_falls_back_when_preferred_amount_is_none`. |
| 11 | Amount and status both differ for the same order. | Both mismatch categories contain the order ID. | `test_reconcile_reports_both_amount_and_status_mismatches`. |
| 12 | Internal or provider input contains duplicate order IDs. | Reconciliation raises `ValueError` instead of silently overwriting a record in a dictionary. | `test_reconcile_rejects_duplicate_internal_order_ids` and `test_reconcile_rejects_duplicate_provider_order_ids`. |
| 13 | An order ID is missing or empty. | Reconciliation raises `ValueError`. | Validation in `reconcile_orders()`. |
| 14 | An order is absent from one side of reconciliation. | It is reported in the corresponding missing-record category. | Existing reconciliation contract and acceptance-matrix tests. |

## Regression tests added

The following seven regression tests were added to `tests/test_contract.py`:

- `test_reconcile_internal_total_against_provider_amount`
- `test_events_without_event_id_are_processed_independently`
- `test_refund_without_event_id_is_ignored`
- `test_reconcile_reports_both_amount_and_status_mismatches`
- `test_reconcile_falls_back_when_preferred_amount_is_none`
- `test_reconcile_rejects_duplicate_internal_order_ids`
- `test_reconcile_rejects_duplicate_provider_order_ids`

## Final verification

The latest recorded full-suite run completed with **219 passed in 0.69s** using:

```powershell
python -m pytest -q
```

The changed files also passed `git diff --check` with no reported whitespace errors. The offline demo was run during integration verification.

## Limitations

- The complete 219-event example dataset was not separately replayed end-to-end; verification is based on the automated test suite and the offline demo.
- No formal performance benchmark was conducted. No execution-time or memory improvement is claimed.
- Events without IDs cannot be reliably deduplicated. Non-refund events without IDs may be processed independently; refund events without IDs are ignored.
- Reconciliation validates order IDs and compares the supported amount/status fields; it is not a general schema-validation framework for arbitrary malformed records.
