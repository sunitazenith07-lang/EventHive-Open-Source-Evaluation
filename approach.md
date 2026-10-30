# approach.md - Required submission

## 1. Baseline
- **Commands run before editing:**
  - `python --version` -> Python 3.15.0
  - `python -m pip install -r requirements-dev.txt`
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result (actual summary):**
  - `62 failed, 150 passed in 0.98s` (Total: 212 tests)
  - Key failures: Idempotency duplicate event tracking (`assert ['EV-000', 'EV-000'] == ['EV-000']`), invalid refund amounts accepted (floats, booleans, negatives, and over-limit amounts), ineligible order refunds, and status mismatches improperly marked as matched during reconciliation.
- **Demo/output observed (`python -m main` on baseline):**
  ```
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```

## 2. Codebase understanding
- **Important files and functions inspected:**
  - `models.py` (`new_order`): Order dictionary constructor initializing `order_id`, `total_paise`, `status`, `payment_status` ("UNPAID"), `refund_due_paise` (0), `refunded_paise` (0), and `processed_event_ids` ([]).
  - `service.py` (`apply_order_event`, `reconcile_orders`): Core business logic for applying events to order state and reconciling internal orders against provider summaries.
  - `fixtures.py` & `data/records.json`: Synthetic datasets representing 150 internal orders, 163 provider records, 219 event examples, and 12 documented reconciliation edge cases.
  - `main.py`: Entry point for local offline reconciliation demo using fixtures.
  - `tests/test_acceptance_matrix.py` & `tests/test_contract.py`: Test suite verifying order lifecycle state machine, idempotency replay, refund eligibility, partial/full refund bounds, and reconciliation matrix.
- **Order lifecycle or data flow traced:**
  - `payment_confirmed`: Sets `payment_status` to `"PAID"`. If the order was already rejected or cancelled, sets `refund_due_paise` to `total_paise` for refunding.
  - `restaurant_accepted`: Valid transition from `"PLACED"` to `"ACCEPTED"`.
  - `restaurant_rejected`: Valid transition from `"PLACED"` to `"REJECTED"`. If payment was already `"PAID"`, computes `refund_due_paise = total_paise`.
  - `cancel_requested`: Valid transition from `"PLACED"` or `"ACCEPTED"` to `"CANCELLED"`. If payment was `"PAID"`, sets `refund_due_paise = total_paise`. Cancellation requests after dispatch (`OUT_FOR_DELIVERY` or `DELIVERED`) are ignored.
  - `dispatch_started`: Valid transition from `"ACCEPTED"` to `"OUT_FOR_DELIVERY"`.
  - `order_delivered`: Valid transition from `"OUT_FOR_DELIVERY"` to `"DELIVERED"`.
  - `refund_processed`: Only valid on eligible orders (`status` in `"REJECTED"`, `"CANCELLED"`, `payment_status == "PAID"`, and `refund_due_paise > 0`). Validates positive integer paise, ensures `amount <= refund_due_paise - refunded_paise`, updates `refunded_paise`, and marks `payment_status = "REFUNDED"` only once `refunded_paise >= refund_due_paise`.
  - `reconcile_orders`: Matches internal and provider records by `order_id`. Validates amounts (supporting both `amount_paise` and `total_paise`) and statuses. Deterministically separates missing records, amount mismatches, and status mismatches.
- **How you confirmed your understanding:**
  - Traced failure stack traces from pytest runs.
  - Verified state transitions against the contract tests in `test_contract.py` and acceptance matrices in `test_acceptance_matrix.py`.

## 3. Investigation and implementation strategy
For each major defect:
- **Issue 1: Idempotency failure on event replay**
  - *Observed symptom:* `test_payment_event_replay_idempotent` failed across 20 test cases. `processed_event_ids` contained duplicate event IDs.
  - *Hypothesis:* `apply_order_event` appended `event_id` unconditionally to `processed_event_ids` without checking whether `event_id` was already processed.
  - *Evidence:* Test failure output: `AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']`.
  - *Fix:* Added an idempotency guard: `if event_id is not None and event_id in out["processed_event_ids"]: return out`. Appended `event_id` only if it was not None.
- **Issue 2: Invalid refund amount and bounds validation**
  - *Observed symptom:* 13 parameter variations of `test_invalid_refund_amounts_are_ignored`, 10 variations of `test_refund_eligibility_matrix`, and 7 variations of `test_refunds_cannot_exceed_due` failed.
  - *Hypothesis:* `service.py` directly added `event.get("amount_paise", 0)` to `refunded_paise` without validating: (a) order refund eligibility, (b) that amount is a positive integer (in Python, `isinstance(True, int)` is True), and (c) that amount does not exceed `refund_due_paise - refunded_paise`.
  - *Evidence:* Negative amounts decreased refunded paise, booleans like `True` added 1 paisa, amounts exceeding outstanding due were processed, and partial refunds marked status as REFUNDED prematurely.
  - *Fix:* Implemented strict eligibility checks (`status in ("REJECTED", "CANCELLED") and payment_status == "PAID" and refund_due_paise > 0`), strict type validation (`isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`), and strict bounds enforcement (`amount <= (refund_due_paise - refunded_paise)`).
- **Issue 3: Reconciliation status mismatch and amount key handling**
  - *Observed symptom:* Status mismatches were categorized into `"matched"`, and in the demo, internal orders with `total_paise` produced false positive amount mismatches.
  - *Hypothesis:* Starter `reconcile_orders` had an intentional flaw where non-matching statuses fell through into `matched`, and it only read `amount_paise`.
  - *Evidence:* `test_reconcile_reports_status_difference` and 7 parameterized test cases failed with status mismatches placed in `matched`.
  - *Fix:* Separated `amount_mismatch` and `status_mismatch`. Both conditions are checked independently and added to their respective mismatch lists. An order is added to `"matched"` only when both amount and status match. Added fallback to `total_paise` if `amount_paise` is not explicitly present.

## 4. Implementation decisions
- **Main changes and why:**
  - Guaranteed immutability using `deepcopy(order)` to ensure caller data is never mutated.
  - Robust defensive handling for missing fields, `None` inputs, or empty lists.
  - Clear separation of `refund_due_paise` and `refunded_paise` to accurately reflect partial refund cycles.
  - Deterministic dictionary ordering using `sorted(..., key=lambda x: str(x))` in reconciliation.
- **Alternatives considered and why rejected:**
  - *In-place dictionary modification:* Rejected because it violates non-mutation contract tests (`test_accept_only_when_placed_and_does_not_mutate_input`, `test_input_order_is_not_mutated`).
  - *Introducing a "PARTIALLY_REFUNDED" status:* Rejected because the acceptance contract specifies that `payment_status` must remain `"PAID"` during partial refunds and switch to `"REFUNDED"` only upon full settlement.
- **Assumptions:**
  - All currency values are strictly positive integers representing paise.
  - Orders without an `event_id` can be processed, but cannot be tracked for deduplication.
  - Order cancellation cannot occur after dispatch (`OUT_FOR_DELIVERY` or `DELIVERED`).

## 5. Verification
- **Tests added or changed:**
  - Preserved all 212 existing tests across `test_acceptance_matrix.py` and `test_contract.py`.
  - Added `tests/test_regression_edge_cases.py` with 10 dedicated test cases covering edge cases from `data/records.json`.
- **Commands run and actual results:**
  - `python -m pytest -q` -> `222 passed in 0.50s` (0 failures, 0 warnings).
  - `python -m main` -> Demo output correctly reconciled:
    - matched: `['ORD-101']`
    - missing_from_provider: `['ORD-103']`
    - missing_from_internal: `['ORD-104']`
    - amount_mismatches: `[]`
    - status_mismatches: `['ORD-102']`
- **Edge cases verified:**
  - Boundary amounts: 1 paisa order with full cancellation and refund.
  - Out-of-order event: Late payment arrival after cancellation or rejection.
  - Conflicting payload replay: Duplicate `event_id` with different amount safely ignored.
  - Empty and malformed records handled without exceptions.
  - Simultaneous amount and status mismatch correctly reported in both mismatch lists.
- **Remaining failures or known limitations:**
  - Zero remaining test failures. All 222 tests pass cleanly.
