# Approach

## 1. Baseline

- **Initial test result:** Not recorded in the retained project notes. No baseline count is reconstructed or assumed.
- **Initial demo output:** The initial output was not retained. During investigation, the reconciliation demo reported amount mismatches for `ORD-101` and `ORD-102`, which led to inspection of the amount-field mapping.
- **Final test result:** `python -m pytest -q` — **219 passed in 0.69s**.

## 2. Codebase understanding

Files inspected included:

- `service.py`: `apply_order_event()` and `reconcile_orders()`.
- `models.py`: order defaults and construction.
- `fixtures.py`: synthetic data used by the offline demonstration.
- `data/records.json` and `data/README.txt`: synthetic records and event examples.
- `tests/test_acceptance_matrix.py` and `tests/test_contract.py`: acceptance and regression coverage.
- `main.py`: offline demonstration entry point.
- `pyproject.toml`, `requirements-dev.txt`, `.gitignore`, and `.github/workflows/tests.yml`: project configuration and CI.

The order begins in `PLACED` with payment status `UNPAID`. Events cover payment confirmation, restaurant acceptance/rejection, cancellation, dispatch, delivery, and refunds. A paid rejected or cancelled order can become eligible for a refund. Reconciliation associates internal and provider summaries by `order_id` and compares amount and status.

## 3. Investigation and implementation

### Issue 1: Duplicate event processing

- **Problem:** Replaying an event with an already processed ID could apply its state change more than once.
- **Change:** Check `processed_event_ids` before applying an identified event and record the ID after processing.
- **Verification:** Existing idempotency tests in the acceptance matrix and contract suite.

### Issue 2: Event ID and event type validation

- **Problem:** Empty, whitespace-only, non-string IDs and unsupported event types should not enter normal transition processing.
- **Change:** Added an allow-list for the seven supported event types. Empty or invalid non-None IDs are rejected. Missing IDs are not stored or used for duplicate detection.
- **Verification:** Acceptance-matrix coverage and the contract regression tests for events without IDs.
- **Important distinction:** Non-refund events without IDs can be processed independently. Refund events without IDs are ignored because a financial event without an ID cannot be reliably protected against replay.

### Issue 3: Refund safety

- **Problem:** Refund processing needs to validate order eligibility, amount type, positive amount, and remaining refundable balance.
- **Change:** Refunds are accepted only for paid rejected/cancelled orders with a positive outstanding balance. The amount must be a positive integer no greater than the outstanding balance. Payment status becomes `REFUNDED` only when the full due amount has been refunded.
- **Additional guard:** Payment confirmation changes payment status only when the current status is `UNPAID`; it does not overwrite a different existing status.
- **Verification:** Existing refund eligibility, invalid amount, partial/full refund, and refund-limit tests, plus `test_refund_without_event_id_is_ignored`.

### Issue 4: Incorrect reconciliation classification

- **Problem:** Amount and status mismatches must be reported independently. A matching amount does not make a record matched when its status differs.
- **Change:** Compare amount and status separately. Add an order to `matched` only when neither comparison differs.
- **Verification:** `test_reconcile_reports_both_amount_and_status_mismatches` and existing reconciliation tests.

### Issue 5: Internal/provider amount-field mapping

- **Problem:** Internal records use `total_paise`, while provider records commonly use `amount_paise`. Reading the wrong field can report a false mismatch.
- **Change:** Read the expected field for each side and fall back to the alternate field when the preferred value is `None`.
- **Verification:** `test_reconcile_internal_total_against_provider_amount` and `test_reconcile_falls_back_when_preferred_amount_is_none`.

### Issue 6: Missing and duplicate reconciliation IDs

- **Problem:** Missing or duplicate order IDs make record matching ambiguous. Duplicate keys would otherwise be silently overwritten when building lookup dictionaries.
- **Change:** Validate both input lists before building dictionaries. Missing/empty IDs and duplicate IDs raise `ValueError`.
- **Verification:** `test_reconcile_rejects_duplicate_internal_order_ids` and `test_reconcile_rejects_duplicate_provider_order_ids`. Missing-ID validation is present in the implementation; no separate new regression test for it is claimed here.

## 4. Implementation decisions

- Use event IDs to prevent replay of identified events.
- Do not treat multiple missing IDs (`None`) as the same event.
- Require an ID for refund events because they change financial state.
- Validate event types and malformed non-None event IDs before transitions.
- Guard payment confirmation so it only changes `UNPAID` to `PAID`.
- Check the outstanding refund balance before accepting another refund.
- Compare reconciliation amount and status independently.
- Support the amount-field names present in the internal and provider records, including fallback when the preferred field is `None`.
- Reject missing and duplicate order IDs rather than silently losing or ambiguously matching records.

## 5. Verification

### Regression tests added

Seven tests were added to `tests/test_contract.py`:

1. `test_reconcile_internal_total_against_provider_amount`
2. `test_events_without_event_id_are_processed_independently`
3. `test_refund_without_event_id_is_ignored`
4. `test_reconcile_reports_both_amount_and_status_mismatches`
5. `test_reconcile_falls_back_when_preferred_amount_is_none`
6. `test_reconcile_rejects_duplicate_internal_order_ids`
7. `test_reconcile_rejects_duplicate_provider_order_ids`

### Recorded commands and results

| Command / check | Recorded result |
|---|---|
| Targeted idempotency tests | 20 passed |
| Targeted refund validation tests | 67 passed |
| Contract tests after missing-ID event fix | 14 passed |
| Contract tests after refund-ID fix | 15 passed |
| `python -m pytest -q` — latest run | **219 passed in 0.69s** |
| `python -m main` | Offline demo run during integration verification |
| `git diff --check` | No errors reported |

### Demo output recorded during integration

```text
matched: ['ORD-101']
missing_from_provider: ['ORD-103']
missing_from_internal: ['ORD-104']
amount_mismatches: []
status_mismatches: ['ORD-102']
```

## 6. Remaining limitations

- The initial baseline test result was not retained, so no before-and-after test-count comparison is claimed.
- Events without IDs cannot be reliably deduplicated. Refund events without IDs are ignored; independent non-refund events without IDs may be processed.
- The final verification establishes that the available test suite passes and the offline demo was run. It does not establish that every event in the synthetic dataset was replayed end-to-end.
- No formal performance benchmark was conducted; no speedup or memory reduction is claimed.
