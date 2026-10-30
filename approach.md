# approach.md — Implementation Approach & Engineering Decisions

## 1. Baseline
- **Commands run before editing:**
  - `python --version` (detected Python 3.14.7 on Windows)
  - `python -m pip install -r requirements-dev.txt` (installed `pytest>=8.0,<10.0` and dependencies)
  - `python -m pytest -q`
  - `python -m main`
- **Initial test result (actual summary):**
  - `62 failed, 150 passed in 1.87s` (total 212 tests).
  - The 62 failures spanned four core areas:
    - 20 failures in `test_payment_event_replay_idempotent` (`processed_event_ids` contained duplicate entries).
    - 13 failures in `test_invalid_refund_amounts_are_ignored` (negative numbers, floats, booleans like `True`/`False`, strings, and amounts over total due were accepted).
    - 10 failures in `test_refund_eligibility_matrix` (refunds were applied to UNPAID, PLACED, ACCEPTED, or already REFUNDED orders).
    - 7 failures in `test_refunds_cannot_exceed_due` (cumulative refunds were allowed to exceed `refund_due_paise`).
    - 7 failures in `test_reconciliation_status_mismatch_matrix`.
    - 5 failures in `test_contract.py` (`test_duplicate_event_is_idempotent`, `test_refund_requires_eligible_order`, `test_refund_must_be_positive`, `test_refund_cannot_exceed_amount_due`, `test_reconcile_reports_status_difference`).
- **Demo/output observed on starter:**
  ```text
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  `ORD-101` and `ORD-102` were falsely marked as amount mismatches because `sample_orders()` stores amount in `total_paise` while `reconcile_orders` only checked `amount_paise`. Furthermore, `status_mismatches` was completely empty even though `ORD-102` had status `ACCEPTED` internally and `CANCELLED` at the provider.

---

## 2. Codebase understanding
- **Important files and functions inspected:**
  - `service.py`: Contains `apply_order_event(order, event)` and `reconcile_orders(internal, provider)`.
  - `models.py`: Helper `new_order(order_id, total_paise, status="PLACED")` defining the internal schema (`order_id`, `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise`, `processed_event_ids`).
  - `fixtures.py` & `main.py`: Demo scenario reconciling sample internal orders against provider summaries.
  - `tests/test_acceptance_matrix.py` & `tests/test_contract.py`: Acceptance and contract suites covering the state transition matrix, replay idempotency, refund eligibility/bounds, and reconciliation determinism.
  - `data/records.json` & `data/README.txt`: Synthetic dataset of 150 internal orders, 163 provider records, and 219 event examples covering edge cases.
- **Order lifecycle and data flow traced:**
  - Forward happy path: `PLACED` -> `ACCEPTED` (via `restaurant_accepted`) -> `OUT_FOR_DELIVERY` (via `dispatch_started`) -> `DELIVERED` (via `order_delivered`).
  - Terminal failure/cancellation branches:
    - `PLACED` -> `REJECTED` (via `restaurant_rejected`). If `payment_status == "PAID"`, sets `refund_due_paise = total_paise`.
    - `PLACED` or `ACCEPTED` -> `CANCELLED` (via `cancel_requested`). If `payment_status == "PAID"`, sets `refund_due_paise = total_paise`.
    - Cancellation attempted after dispatch (`OUT_FOR_DELIVERY` or `DELIVERED`) must be ignored and retain current status.
  - Asynchronous payment handling:
    - If `payment_confirmed` arrives after the order was already `REJECTED` or `CANCELLED` while `UNPAID`, payment flips to `PAID` and `refund_due_paise` is initialized to `total_paise`.
  - Refund processing:
    - Must verify eligibility: `status in ("REJECTED", "CANCELLED")`, `payment_status == "PAID"`, and `refund_due_paise > 0`.
    - Must validate amount: positive integer, non-boolean, and `amount <= refund_due_paise - refunded_paise`.
    - Cumulative tracking: partial refunds keep `payment_status == "PAID"`; status changes to `REFUNDED` only when `refunded_paise >= refund_due_paise`.
- **How understanding was confirmed:**
  - Ran targeted unit tests against the transition matrix.
  - Verified edge cases against the `records.json` dataset and the edge-case catalog in `data/README.txt`.

---

## 3. Investigation and implementation strategy

### Issue 1: Event Replay Idempotency Defect
- **Observed symptom:** Every test replaying an event failed with duplicate items in `processed_event_ids` (e.g. `AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']`).
- **Hypothesis:** `apply_order_event` lacked an idempotency check on `event_id` and blindly appended every `event_id` to `processed_event_ids`.
- **Evidence:** Line 43 in starter `service.py`: `out["processed_event_ids"].append(event_id)` without checking membership.
- **Fix chosen:** Added an upfront idempotency check:
  ```python
  if event_id is not None and event_id in out["processed_event_ids"]:
      return out
  ```
  Only append non-null `event_id` upon successful initial processing.

### Issue 2: Unsafe Refund Processing & Eligibility Leaks
- **Observed symptom:** 30+ tests failed where invalid amounts (negative numbers, floats, `True`/`False`, strings, over-refund amounts) or ineligible orders (unpaid, placed, accepted, delivered, or already refunded) were mutated.
- **Hypothesis:** Starter code unconditionally executed `out["refunded_paise"] += event.get("amount_paise", 0)` without eligibility or type constraints.
- **Evidence:** `out["refunded_paise"]` was modified even when `payment_status` was `"UNPAID"` or when amount was negative.
- **Fix chosen:** Enforced strict eligibility and integer bounds:
  ```python
  is_eligible = (
      out.get("status") in ("REJECTED", "CANCELLED")
      and out.get("payment_status") == "PAID"
      and out.get("refund_due_paise", 0) > 0
  )
  amount = event.get("amount_paise")
  if (
      is_eligible
      and isinstance(amount, int)
      and not isinstance(amount, bool)
      and amount > 0
  ):
      outstanding = out.get("refund_due_paise", 0) - out.get("refunded_paise", 0)
      if amount <= outstanding:
          out["refunded_paise"] += amount
          if out["refunded_paise"] >= out.get("refund_due_paise", 0):
              out["payment_status"] = "REFUNDED"
  ```

### Issue 3: Reconciliation Logic Defect (False Positives and Ignored Status)
- **Observed symptom:** Status mismatches were never reported and erroneously appeared in `matched`. Also, internal orders using `total_paise` failed amount comparison against provider records using `amount_paise`.
- **Hypothesis:** Starter `reconcile_orders` compared `a.get("amount_paise") != b.get("amount_paise")` (giving `None != 45900` when `total_paise` was used), and had a deliberate bug where non-matching statuses fell into `report["matched"]`.
- **Evidence:** Comments in starter code: `# Deliberate starter defect: mismatched statuses may be called matched.`
- **Fix chosen:** Normalized amount field extraction to support both `amount_paise` and `total_paise`, separated amount and status evaluations, populated `status_mismatches` independently, and only populated `matched` when both amount and status matched.

---

## 4. Implementation decisions
- **Main changes and why:**
  - Implemented immutable update pattern via `deepcopy(order)` to ensure caller dictionary is never mutated in-place.
  - Implemented guard clauses for non-dictionary `order` and `event` arguments to prevent unhandled runtime exceptions.
  - Added support for asynchronous late payments: if an order was rejected/cancelled while `UNPAID` and `payment_confirmed` arrives subsequently, `refund_due_paise` is initialized to `total_paise`.
  - Added optional stretch function `summarize_orders_by_state(orders)` providing deterministic distribution counts by order status.
- **Alternatives considered and why rejected:**
  - *In-place mutation:* Rejected because caller order objects would be corrupted on failed/replay events and tests verify immutability (`test_input_order_is_not_mutated`).
  - *Raising exceptions on invalid events:* Rejected because the problem statement explicitly specifies handling malformed events gracefully without corrupting state.
- **Assumptions:**
  - Order amounts and refund amounts are always non-negative integers representing paise.
  - An event with `event_id` is unique and idempotent across retries.
  - Once an order reaches `OUT_FOR_DELIVERY` or `DELIVERED`, customer cancellation is disallowed.

---

## 5. Verification
- **Tests added or changed:**
  - Existing test suites preserved untouched (0 tests deleted or modified).
  - Added `tests/test_regression_and_edge_cases.py` (10 tests) covering:
    - Idempotent duplicate cancellations.
    - Late payment confirmation on previously rejected/cancelled orders.
    - Post-delivery cancellation rejection.
    - Strict refund overage protection and boundary validation.
    - Python boolean type rejection (`True`/`False` treated as invalid, not `1`/`0`).
    - Malformed input resilience (non-dict inputs, missing `event_id`).
    - Simultaneous amount and status mismatch in reconciliation.
    - Graceful handling of invalid entries in reconciliation.
    - Order state summarization stretch function.
- **Commands run and actual results:**
  - `python -m pytest -q` -> `222 passed in 0.45s` (100% passing across all suites).
  - `python -m main` ->
    ```text
    matched: ['ORD-101']
    missing_from_provider: ['ORD-103']
    missing_from_internal: ['ORD-104']
    amount_mismatches: []
    status_mismatches: ['ORD-102']
    ```
- **Edge cases verified:**
  - Overlapping amount and status mismatch (`ORD-1078` in `records.json`).
  - Events with missing `event_id` processed safely without appending `None`.
  - Replay of identical and conflicting events prevented by idempotency check.
- **Remaining failures or known limitations:**
  - Zero remaining test failures. All 222 tests pass cleanly.
