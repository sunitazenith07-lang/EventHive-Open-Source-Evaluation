# challenges.md — COMPULSORY Submission

## 1. Challenge or confusing behaviour
Three notable technical challenges and non-obvious behaviours arose during investigation:

1. **Python Boolean Subclass Trap in Amount Validation:**
   In Python, `bool` is a direct subclass of `int` (`issubclass(bool, int) is True`), and boolean literals evaluate numerically (`int(True) == 1`, `int(False) == 0`). When initially filtering valid integer refund amounts using `isinstance(amount, int) and amount > 0`, events with `amount_paise=True` bypassed validation and processed a 1-paise refund.
   
2. **Schema Key Asymmetry Between Internal Models and Provider Records:**
   In `fixtures.py` and `main.py`, internal orders created via `models.new_order` store monetary values under `total_paise`, whereas provider records use `amount_paise`. Furthermore, tests in `test_acceptance_matrix.py` pass dictionaries with `amount_paise` on both sides. The starter `reconcile_orders` strictly accessed `a.get("amount_paise")`, returning `None` for internal orders and falsely classifying matching orders as amount mismatches.

3. **Multi-Dimensional Mismatch Classification in Reconciliation:**
   Reconciliation requires reporting missing records, amount mismatches, and status mismatches separately and deterministically. If an order diverges in both amount and status (such as `ORD-1078` in `data/records.json`), it must be included in both `amount_mismatches` and `status_mismatches`, while being strictly excluded from `matched`. The starter code used a naive `if amount_mismatch: ... else: matched.append(...)`, which omitted status checking entirely.

---

## 2. Evidence
- **Python Boolean Trap:**
  Running `pytest` on an initial draft with `isinstance(amount, int) and amount > 0` yielded:
  ```text
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
  E   assert 1 == 0
  ```
- **Schema Asymmetry in Offline Demo:**
  Running `python -m main` on starter code gave:
  ```text
  amount_mismatches: ['ORD-101', 'ORD-102']
  ```
  Even though `ORD-101` had `total_paise=45900` internally and `amount_paise=45900` at the provider.
- **Reconciliation Status Neglect:**
  Starter code test output:
  ```text
  FAILED tests/test_acceptance_matrix.py::test_reconciliation_status_mismatch_matrix[PLACED-ACCEPTED]
  E   AssertionError: assert ['O'] == [] (order 'O' was found in matched instead of status_mismatches)
  ```

---

## 3. What I tried
1. **For the Boolean Trap:**
   - Experimented with `type(amount) is int`. While effective, it disallows standard integer subclasses if extended.
   - Decided on `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`. This explicitly documents the domain rule (booleans are not valid monetary amounts).

2. **For Schema Asymmetry:**
   - Inspected `models.py`, `fixtures.py`, `data/records.json`, and test fixtures in `tests/test_acceptance_matrix.py`.
   - Discovered that synthetic internal orders use `total_paise` while synthetic provider summaries use `amount_paise`, but reconciliation unit tests use `amount_paise` on both sides.
   - Tested normalizing amount extraction:
     ```python
     a_amount = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
     b_amount = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")
     ```

3. **For Multi-Dimensional Reconciliation:**
   - Evaluated using separate disjoint passes vs single-loop independent condition flags.
   - Formulated boolean flags `amount_diff` and `status_diff`. If either is True, the order is appended to the corresponding report list; only when `not amount_diff and not status_diff` does the order enter `matched`.

---

## 4. Resolution
- **Root Causes:**
  - Idempotency was missing because `apply_order_event` lacked an early return check against `out["processed_event_ids"]`.
  - Type validation was missing in refund processing, allowing non-integers, floats, negative values, and booleans to mutate state.
  - Eligibility rules were not checked (unpaid or non-cancelled/non-rejected orders could be refunded).
  - Reconciliation ignored status differences and failed to accommodate both `total_paise` and `amount_paise` dictionary keys.
- **Changes Made:**
  - Added idempotency filter: `if event_id is not None and event_id in out["processed_event_ids"]: return out`.
  - Added comprehensive eligibility, type, and bound verification before mutating `refunded_paise`.
  - Updated `reconcile_orders` to check both amount and status independently, correctly classifying orders with single or dual mismatches.

---

## 5. Proof and regression prevention
- **Demonstration Tests:**
  - `test_invalid_refund_amounts_are_ignored[True]` and `test_invalid_refund_amounts_are_ignored[False]` now pass.
  - Added `test_boolean_refund_amounts_are_rejected` in `tests/test_regression_and_edge_cases.py` to permanently guard against the boolean-as-int trap.
  - Added `test_reconciliation_simultaneous_amount_and_status_mismatch` to verify that an order with both discrepancies is recorded in both mismatch lists.
  - Added `test_duplicate_cancellation_event_is_idempotent` ensuring cancellation idempotency beyond payment replay.
- **What could still break:**
  - If external callers supply corrupted records containing circular structures, `deepcopy` could hit recursion limits. Guarding against non-dict inputs at the function boundaries mitigates typical malformed data.

---

## 6. Unresolved challenge or next step
- In large-scale high-throughput production (e.g. millions of orders per hour), maintaining `processed_event_ids` as an in-memory Python list would result in $O(N)$ lookup times as event history grows. For this offline evaluation, event lists are small ($\le 10$ events per order). In a production architecture, this would be backed by a bounded Redis set with TTL or a relational uniqueness constraint on `(order_id, event_id)` with index lookups ($O(1)$).
