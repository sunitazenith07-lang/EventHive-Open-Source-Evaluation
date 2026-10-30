# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: Python 3.13.14
- Command run: `python -m pytest -q`
- Actual test summary:
  - Baseline (untouched starter): `62 failed, 150 passed in 0.64s` (Total 212 tests)
  - Final (after defect fixes + regression suite): `222 passed in 0.33s` (Total 222 tests)
  - Offline demo (`python -m main`):
    - Baseline: `matched: []`, `missing_from_provider: ['ORD-103']`, `missing_from_internal: ['ORD-104']`, `amount_mismatches: ['ORD-101', 'ORD-102']`, `status_mismatches: []`
    - Final: `matched: ['ORD-101']`, `missing_from_provider: ['ORD-103']`, `missing_from_internal: ['ORD-104']`, `amount_mismatches: []`, `status_mismatches: ['ORD-102']`

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | Replaying identical `event_id` across event types (`payment_confirmed`, `cancel_requested`, `refund_processed`) | Second event invocation is ignored; order state, payment status, and refund amounts remain unchanged; `event_id` is recorded only once in `processed_event_ids`. | PASSED. Event replay returned untouched order copy; `processed_event_ids` contains single entry. | `test_payment_event_replay_idempotent`, `test_idempotency_across_different_event_types` |
| 2 | Cancellation request received after order dispatch (`OUT_FOR_DELIVERY` or `DELIVERED`) | Cancellation request is rejected; order state remains `OUT_FOR_DELIVERY` or `DELIVERED`; `refund_due_paise` remains 0. | PASSED. Status did not mutate to `CANCELLED` and no refund was allocated. | `test_cancel_after_dispatch_is_ignored`, `test_cannot_cancel_out_for_delivery_or_delivered` |
| 3 | Non-integer, negative, float, and boolean refund amounts (`True`, `False`, `None`, `-10`, `0.5`, `10000`) | Boolean values (which subclass `int` in Python), non-integers, non-positives, and amounts exceeding outstanding refundable balance are rejected with no mutation of `refunded_paise`. | PASSED. `refunded_paise` stayed 0 and `payment_status` remained `PAID`. | `test_invalid_refund_amounts_are_ignored`, `test_boolean_and_type_coercion_safety_in_refunds` |
| 4 | Multiple sequential partial refunds summing to exact `total_paise` | Each partial refund increments `refunded_paise` while `payment_status` stays `PAID`; upon the final refund matching `refund_due_paise`, `payment_status` transitions to `REFUNDED`; further refunds rejected. | PASSED. Exact transition sequence observed: `PAID` -> `PAID` -> `REFUNDED`; overage rejected. | `test_valid_partial_and_full_refunds`, `test_multiple_partial_refunds_reaching_exact_total` |
| 5 | Simultaneous amount mismatch and status mismatch on the same order in reconciliation | The order ID is reported deterministically in both `amount_mismatches` and `status_mismatches`, and excluded from `matched`. | PASSED. Order present in both `amount_mismatches` and `status_mismatches`; excluded from `matched`. | `test_reconciliation_simultaneous_amount_and_status_mismatch` |
| 6 | Late payment confirmation after restaurant rejection (`PLACED` -> `REJECTED` -> `payment_confirmed`) | When payment confirms after rejection, payment status becomes `PAID` and `refund_due_paise` is initialized to `total_paise`. | PASSED. `refund_due_paise` correctly set to `4500` and order unlocked for full refund. | `test_payment_confirmed_after_rejection_sets_refund_due` |

## Regression tests added
List the defects fixed and the tests added to prevent them from returning.

1. **Defect: Event Replay Duplicate Accumulation**
   - *Fix:* Idempotency check added at entry of `apply_order_event`. If `event_id` is already present in `processed_event_ids`, return the order unmodified.
   - *Regression Test:* `test_idempotency_across_different_event_types` in `tests/test_regression_and_edge_cases.py`.
2. **Defect: Ineligible & Unbounded Refund Processing**
   - *Fix:* Enforced strict eligibility (`status in ("REJECTED", "CANCELLED") and payment_status == "PAID" and refund_due_paise > 0`), strict type validation (`isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`), and capped against `due - refunded`. Transition `payment_status` to `"REFUNDED"` only when `refunded == due`.
   - *Regression Tests:* `test_multiple_partial_refunds_reaching_exact_total`, `test_boolean_and_type_coercion_safety_in_refunds`, `test_payment_confirmed_after_rejection_sets_refund_due`.
3. **Defect: Reconciliation Status Ignored and Incompatible Key Names**
   - *Fix:* Added status comparison (`a_status != b_status`), populated `status_mismatches`, resolved amount retrieval across `amount_paise` and `total_paise`, and ensured orders with both mismatches appear in both categories.
   - *Regression Tests:* `test_reconciliation_simultaneous_amount_and_status_mismatch`, `test_reconciliation_supports_both_total_paise_and_amount_paise`, `test_reconciliation_invalid_and_empty_inputs`.
4. **Defect: Malformed / Empty Input State Corruption**
   - *Fix:* Added type guards for `order`, `event`, `internal`, and `provider`, gracefully returning clean structures without unhandled exceptions.
   - *Regression Test:* `test_safe_handling_of_malformed_and_none_inputs`.
5. **Stretch Feature: Awaiting Refund CSV Export**
   - *Feature:* Added `export_awaiting_refund_csv(orders, filepath=None)` to export orders where `refund_due_paise > refunded_paise`.
   - *Test:* `test_stretch_export_awaiting_refund_csv`.

## Remaining failures or limitations
List any known failing tests or unresolved behaviours honestly.

- **Current Failing Tests:** None (0 failures, 222 passed).
- **Known Limitations:**
  - Events without an `event_id` cannot be deduplicated by `event_id`; they are applied sequentially if valid.
  - The reconciliation logic assumes order IDs are unique within a single provider or internal list. Duplicate order IDs within the same list will overwrite previous entries in the hash map.
