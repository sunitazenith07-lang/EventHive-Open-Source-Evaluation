# approach.md — Required submission

## 1. Baseline
- **Commands run before editing**:
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result**:
  The untouched starter reported **62 failed, 150 passed in 2.91s**. Specifically:
  - `reconcile_orders` failed to detect status mismatches when amounts matched, erroneously categorizing mismatched orders into `matched`.
  - `reconcile_orders` failed to report orders with both amount mismatches and status mismatches simultaneously in both mismatch categories.
  - `apply_order_event` did not enforce strict refund bounds or order eligibility: invalid amounts (negatives, floats, excess amounts) were directly added to `refunded_paise`, and refunds were permitted on orders not in `CANCELLED` or `REJECTED` state or unpaid orders.
  - Partial refunds could prematurely trigger `REFUNDED` payment status when `refunded_paise >= refund_due_paise` due to loose comparison logic on uninitialized due amounts.
  - Malformed events (missing `event_id`, invalid event `type`, non-dict events) were not rejected cleanly and mutated internal event tracking.
- **Demo/output observed**:
  Baseline `python -m main` reported `status_mismatches: []` even though ORD-102 had different internal/provider statuses.

## 2. Codebase understanding
- **Important files and functions inspected**:
  - `service.py`: Contains `apply_order_event(order: dict, event: dict)` and `reconcile_orders(internal: list[dict], provider: list[dict])`.
  - `models.py`: Defines `new_order(order_id, total_paise, status)` initializing order state, integer amounts, and event tracking structures.
  - `fixtures.py` and `main.py`: Sample orders and provider records used for demonstration.
  - `tests/test_contract.py` & `tests/test_acceptance_matrix.py`: Contract assertions and 200+ parametrized test cases verifying state transition matrices, idempotency, refund limits, and reconciliation accuracy.
  - `data/records.json`: Synthetic dataset containing 150 internal orders, 163 provider records, 219 event examples, and the 12 edge cases catalog.
- **Order lifecycle and data flow traced**:
  - **Happy Delivery Flow**: `PLACED` $\rightarrow$ (`restaurant_accepted`) $\rightarrow$ `ACCEPTED` $\rightarrow$ (`dispatch_started`) $\rightarrow$ `OUT_FOR_DELIVERY` $\rightarrow$ (`order_delivered`) $\rightarrow$ `DELIVERED`.
  - **Rejection Flow**: `PLACED` $\rightarrow$ (`restaurant_rejected`) $\rightarrow$ `REJECTED`. If order is `PAID`, `refund_due_paise` becomes `total_paise`.
  - **Cancellation Flow**: `PLACED` or `ACCEPTED` $\rightarrow$ (`cancel_requested`) $\rightarrow$ `CANCELLED`. If `PAID`, `refund_due_paise` becomes `total_paise`. Cancellation requests after dispatch (`OUT_FOR_DELIVERY`) are strictly ignored (remain `OUT_FOR_DELIVERY`).
  - **Payment Flow**: `payment_confirmed` sets `payment_status` to `PAID`. If the order was already in `CANCELLED` or `REJECTED` state prior to payment confirmation, `refund_due_paise` is updated to `total_paise`.
  - **Refund Processing**: `refund_processed` applies only to paid orders in `CANCELLED` or `REJECTED` state with integer `amount_paise > 0` and `amount_paise <= refund_due_paise - refunded_paise`. `payment_status` transitions to `REFUNDED` only when `refunded_paise == refund_due_paise`.
  - **Idempotency**: Every processed event records its `event_id` in `processed_event_ids`. Duplicate event IDs result in an immediate no-op return.
- **How understanding was confirmed**:
  Traced edge cases through unit tests in `tests/test_contract.py` and verified all matrix transitions against `test_order_state_transition_matrix` and `test_refund_eligibility_matrix`.

## 3. Investigation and implementation strategy
For each major defect:

- **Issue 1: Defective refund validation and premature full-refund status**
  - *Symptom*: Negative amounts, floating point values, non-numeric values, and amounts exceeding `refund_due_paise` were added to `refunded_paise`. Unpaid or active orders accepted refund events.
  - *Hypothesis*: `apply_order_event` lacked precondition checks for order status (`CANCELLED`/`REJECTED`), payment status (`PAID`), strict type check (`type(amount) is int`), positive sign (`amount > 0`), and available balance (`amount <= due - refunded`).
  - *Fix*: Implemented strict validation:
    ```python
    if (out.get("status") in ("CANCELLED", "REJECTED")
            and out.get("payment_status") == "PAID"
            and type(amount) is int and amount > 0
            and type(due) is int and due > 0
            and type(refunded) is int and 0 <= refunded <= due
            and amount <= due - refunded):
        out["refunded_paise"] += amount
        if out["refunded_paise"] == due:
            out["payment_status"] = "REFUNDED"
    ```

- **Issue 2: Status mismatches omitted in reconciliation**
  - *Symptom*: Orders with identical amounts but differing lifecycle statuses (e.g., internal `PLACED` vs provider `CANCELLED`) were appended to `matched` and omitted from `status_mismatches`. Furthermore, orders with both amount and status differences only recorded the amount mismatch.
  - *Hypothesis*: `reconcile_orders` utilized an exclusive `if/else` block that checked amount equality and defaulted to `matched`.
  - *Fix*: Decoupled the checks into separate flags `amount_mismatch` and `status_mismatch`. Orders are appended to `amount_mismatches` if amounts differ, to `status_mismatches` if statuses differ, and to `matched` only when neither mismatch is present.

- **Issue 3: Event idempotency and malformed event safety**
  - *Symptom*: Events with empty, invalid, or missing `event_id` or `type` were appended to `processed_event_ids`, and duplicate events could re-trigger state mutations.
  - *Hypothesis*: Pre-validation guard was missing before checking event types and mutating the order dictionary.
  - *Fix*: Added comprehensive guard:
    ```python
    valid_kinds = {"payment_confirmed", "restaurant_accepted", "restaurant_rejected",
                   "cancel_requested", "dispatch_started", "order_delivered",
                   "refund_processed"}
    if (not isinstance(event_id, str) or not event_id
            or event_id in processed_event_ids
            or not isinstance(kind, str) or kind not in valid_kinds):
        return out
    ```

- **Issue 4: Late payment confirmation after cancellation/rejection**
  - *Symptom*: If `cancel_requested` or `restaurant_rejected` arrived before `payment_confirmed` (webhook latency or race condition), `refund_due_paise` remained 0 even after payment was confirmed, preventing subsequent refund processing.
  - *Hypothesis*: `payment_confirmed` must compute `refund_due_paise` if the order is already in a terminal cancelled/rejected state.
  - *Fix*: Added conditional check on `payment_confirmed`:
    ```python
    if kind == "payment_confirmed":
        out["payment_status"] = "PAID"
        if out.get("status") in ("CANCELLED", "REJECTED"):
            out["refund_due_paise"] = out.get("total_paise", 0)
    ```

## 4. Implementation decisions
- **Main changes and why**:
  - Implemented immutable updates via `deepcopy` in `apply_order_event` to guarantee caller inputs are never mutated.
  - Used exact integer paise math throughout to prevent floating point inaccuracies.
  - Ensured deterministic sorting of keys in `reconcile_orders` via `sorted(set(left) | set(right), key=lambda x: str(x))` to guarantee reproducible report ordering.
- **Alternatives considered and why rejected**:
  - Considered in-place mutation of `order` for slight speedup, but rejected because pure functional behavior is essential in event-driven systems and prevents side-effect corruption during replays.
  - Considered raising exceptions for invalid events, but rejected because resilient event processing pipelines must safely ignore malformed/unknown events without crashing worker threads.
- **Assumptions**:
  - Currency is strictly denominated in integer paise.
  - Orders cannot be cancelled after `dispatch_started` has moved state to `OUT_FOR_DELIVERY`.
  - Provider reconciliation is keyed on unique `order_id`.

## 5. Verification
- **Tests added or changed**:
  - Updated `test_unknown_event_does_not_mutate_order_state` to verify exact object preservation.
  - Added `test_malformed_event_is_ignored` covering empty dicts, missing IDs, and non-string types.
  - Added `test_duplicate_refund_event_is_idempotent` in `tests/test_contract.py`.
  - Added `test_reconcile_reports_amount_and_status_differences_separately`.
  - Added `test_payment_confirmed_after_cancellation_marks_refund_due` and `test_payment_confirmed_after_rejection_marks_refund_due`.
- **Commands run and actual results**:
  - `python -m pytest -q`: 221 passed in 0.72s on the latest recorded final run.
  - `python -m main`: Successfully printed expected reconciliation partitions:
    - `matched`: `[]`
    - `missing_from_provider`: `['ORD-103']`
    - `missing_from_internal`: `['ORD-104']`
    - `amount_mismatches`: `['ORD-101', 'ORD-102']`
    - `status_mismatches`: `['ORD-102']`
- **Edge cases verified**:
  - Replay of identical refund event.
  - Refund amount equal to zero or negative integers.
  - Cumulative partial refunds exceeding refundable due amount.
  - Cancellation after dispatch.
  - Discrepancy reporting for missing provider orders, missing internal orders, and dual amount/status mismatches.
- **Remaining failures or known limitations**:
  - No test failures remain. Reconciliation still collapses duplicate rows for the same order ID to the last row in each input list.
