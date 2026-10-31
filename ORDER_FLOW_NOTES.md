# ORDER_FLOW_NOTES.md

## 1. Example order-event sequence

Example order: `ORD-DEMO-01`, total amount `1000` paise, initially `PLACED` and `UNPAID`.

| Step | Event | Expected order/payment/refund state | Result |
|---|---|---|---|
| 1 | `payment_confirmed` (`E1`) | `PLACED`, `PAID`, refund due `0`, refunded `0` | `PLACED`, `PAID`, refund due `0`, refunded `0` |
| 2 | `restaurant_accepted` (`E2`) | `ACCEPTED`, `PAID`, refund due `0`, refunded `0` | `ACCEPTED`, `PAID`, refund due `0`, refunded `0` |
| 3 | `dispatch_started` (`E3`) | `OUT_FOR_DELIVERY`, `PAID`, refund due `0`, refunded `0` | `OUT_FOR_DELIVERY`, `PAID`, refund due `0`, refunded `0` |
| 4 | `cancel_requested` (`E4`) | Cancellation after dispatch is ignored; remain `OUT_FOR_DELIVERY`, `PAID`, refund due `0`, refunded `0` | `OUT_FOR_DELIVERY`, `PAID`, refund due `0`, refunded `0` |

Each identified event is recorded in `processed_event_ids`. A repeated event ID is ignored. Unsupported event types and invalid IDs (empty, whitespace-only, or non-string values) are ignored. Non-refund events without IDs can be processed independently but cannot be deduplicated by ID.

## 2. Three edge cases

### 1. Cancellation after dispatch

- **Input:** Start with an order in `OUT_FOR_DELIVERY`, then apply `cancel_requested` with event ID `E-CANCEL`.
- **Expected:** The cancellation does not change the order because dispatch has already started.
- **Result:** The order remains `OUT_FOR_DELIVERY`; payment and refund values remain unchanged.
- **Verifying test:** `test_cancel_after_dispatch_is_ignored` in `tests/test_contract.py`.

### 2. Partial refund must not mark payment as fully refunded

- **Input:** Start with a `CANCELLED` order whose payment status is `PAID` and refund due is `1000` paise. Apply `refund_processed` with event ID `R1` and amount `400` paise.
- **Expected:** Record the partial refund, but do not mark payment as fully refunded.
- **Result:** `refunded_paise` becomes `400`; `payment_status` remains `PAID`.
- **Verifying test:** `test_partial_refund_is_not_marked_complete` in `tests/test_contract.py`, plus the partial/full refund tests in `tests/test_acceptance_matrix.py`.

### 3. Refund event without an event ID

- **Input:** Start with a `CANCELLED` order, payment status `PAID`, and refund due `1000` paise. Apply `refund_processed` for `400` paise without an `event_id`.
- **Expected:** Do not process the refund because it cannot be reliably protected against replay.
- **Result:** `refunded_paise` remains `0`, `payment_status` remains `PAID`, and no ID is recorded.
- **Verifying test:** `test_refund_without_event_id_is_ignored` in `tests/test_contract.py`.

## 3. Reconciliation behaviour

`reconcile_orders(internal, provider)` associates records by `order_id` and returns five categories:

- `matched`
- `missing_from_provider`
- `missing_from_internal`
- `amount_mismatches`
- `status_mismatches`

Internal amounts are read from `total_paise`, falling back to `amount_paise` when the preferred value is `None`. Provider amounts are read from `amount_paise`, falling back to `total_paise` when the preferred value is `None`.

Amount and status comparisons are independent. If both differ, the order ID is included in both mismatch lists. An order is added to `matched` only when both amount and status agree. Missing or duplicate order IDs raise `ValueError`, avoiding silent dictionary overwrites or ambiguous reconciliation.

Regression tests added for these cases:

- `test_reconcile_internal_total_against_provider_amount`
- `test_reconcile_reports_both_amount_and_status_mismatches`
- `test_reconcile_falls_back_when_preferred_amount_is_none`
- `test_reconcile_rejects_duplicate_internal_order_ids`
- `test_reconcile_rejects_duplicate_provider_order_ids`

## 4. Assumptions and limitations

### Event transitions and IDs

- Supported event types are `payment_confirmed`, `restaurant_accepted`, `restaurant_rejected`, `cancel_requested`, `dispatch_started`, `order_delivered`, and `refund_processed`.
- A restaurant can accept or reject an order only while it is `PLACED`.
- Dispatch starts only from `ACCEPTED`; delivery is recorded only from `OUT_FOR_DELIVERY`.
- Cancellation is accepted only from `PLACED` or `ACCEPTED`; a request after dispatch is ignored.
- A repeated valid event ID is ignored. Empty, whitespace-only, and non-string IDs are rejected.
- Non-refund events without IDs can be processed independently, but replay protection cannot be guaranteed for them.
- Refund events require an event ID.

### Refunds

- Amounts are integer paise, not floating-point rupees.
- A paid order that is rejected or cancelled has its full `total_paise` recorded as `refund_due_paise`.
- A refund must be a positive integer and cannot exceed the outstanding refund due.
- Refunds are accepted only for `REJECTED` or `CANCELLED` orders with payment status `PAID` and a positive outstanding balance.
- Partial refunds increase `refunded_paise` while payment status remains `PAID`.
- Payment status changes to `REFUNDED` only when the full refund due has been processed.

### Remaining limitations

- Events without IDs cannot be reliably deduplicated.
- Reconciliation supports the documented amount-field alternatives and validates missing/duplicate order IDs; it does not validate every possible malformed field in arbitrary input.
- The offline demo and automated tests were run, but the full synthetic event dataset was not replayed end-to-end as a separate verification.
- Performance improvements have not been benchmarked, and no performance gains are claimed.
