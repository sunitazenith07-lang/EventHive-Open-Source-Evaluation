# challenges.md — Challenges & Debugging (COMPULSORY)

## 1. Challenge or Confusing Behaviour
During the initial investigation and fix implementation, three notable technical challenges arose:

1. **Python Boolean Subclass Trap during Type Validation:**
   In `test_invalid_refund_amounts_are_ignored[True]`, the test failed because passing `True` resulted in a refund of 1 paise being applied instead of being ignored.
2. **Schema Inconsistency between Internal Orders and External Provider Records:**
   Running `python -m main` showed `amount_mismatches: ['ORD-101', 'ORD-102']` even though `ORD-101` had identical values (45900 paise, PLACED) in both internal and provider datasets.
3. **Dual Dimensional Mismatches in Reconciliation:**
   In `data/records.json`, `ORD-1078` differs in both financial amount (999 vs 1000 paise) and operational status (`DELIVERED` vs `PLACED`). A naive `if/elif` reconciliation flow would silently swallow the status discrepancy if amount mismatch was checked first.

## 2. Evidence
- **Boolean Trap Evidence:**
  When checking `isinstance(amount, int) and amount > 0`:
  ```text
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
  assert 1 == 0
    +1
    -0
  ```
  In Python, `bool` is an exact subclass of `int` (`issubclass(bool, int) is True`), and `True == 1` and `False == 0`. Therefore, `isinstance(True, int)` evaluated to `True`, allowing boolean flags to pass integer checks and mutate financial state.

- **Schema Inconsistency Evidence:**
  Inspecting `models.new_order()`:
  ```python
  def new_order(order_id: str, total_paise: int, status: str="PLACED") -> dict:
      return {"order_id": order_id, "total_paise": total_paise, ...}
  ```
  Inspecting `fixtures.sample_provider_orders()`:
  ```python
  {"order_id": "ORD-101", "amount_paise": 45900, "status": "PLACED"}
  ```
  Because the starter code in `service.py` read only `a.get("amount_paise")`, `a.get("amount_paise")` returned `None`. Comparing `None != 45900` caused false amount mismatches on valid matching orders.

- **Dual Mismatch Evidence from `records.json`:**
  Inspecting `ORD-1078` in `data/records.json`:
  ```json
  // internal order
  {"order_id": "ORD-1078", "total_paise": 999, "status": "DELIVERED", ...}
  // provider record
  {"order_id": "ORD-1078", "amount_paise": 1000, "status": "PLACED", ...}
  ```

## 3. What I Tried
- **For the Boolean Trap:**
  1. Experimented with `type(amount) is int`. While this excluded `bool`, it would disallow custom `int` subclasses if used in future extensions.
  2. Tested `isinstance(amount, int) and not isinstance(amount, bool) and amount > 0`. This cleanly filtered out `True`, `False`, `0`, and negative numbers while permitting all true integers.
- **For the Schema Inconsistency:**
  1. Checked whether `models.py` could be modified. However, changing `new_order()` might break external consumers or other test suites expecting `total_paise`.
  2. Implemented an accessor helper `_get_amount(record)` inside `reconcile_orders` that inspects `amount_paise` first, falling back to `total_paise`. This preserved compatibility across both internal models and provider summaries.
- **For the Dual Mismatch:**
  1. Evaluated whether an order should belong to only one mismatch bucket.
  2. Inspected requirement 6: *"Report missing records, amount mismatches and status mismatches separately and deterministically."*
  3. Inspected `data/records.json` edge-case catalog: *"amount and status mismatches individually and together"*. This confirmed that orders differing on both dimensions must be recorded in both lists.

## 4. Resolution
- **Boolean Trap Resolution:**
  Implemented strict compound type-checking:
  ```python
  if isinstance(amount, int) and not isinstance(amount, bool) and amount > 0:
  ```
  This guarantees that only positive integer values are processed as refunds.
- **Schema Resolution:**
  Added the fallback amount reader:
  ```python
  def _get_amount(record: dict):
      if "amount_paise" in record:
          return record.get("amount_paise")
      return record.get("total_paise")
  ```
  This immediately resolved the false amount mismatches in `main.py` demo and enabled transparent reconciliation across diverse data schemas.
- **Dual Mismatch Resolution:**
  Structured the reconciliation checks as non-exclusive branches:
  ```python
  if has_amount_mismatch:
      report["amount_mismatches"].append(key)
  if has_status_mismatch:
      report["status_mismatches"].append(key)
  if not has_amount_mismatch and not has_status_mismatch:
      report["matched"].append(key)
  ```

## 5. Proof and Regression Prevention
- **Proof:**
  - Ran `python -m pytest -q` confirming all 212 baseline tests passed.
  - Added specific regression tests in `tests/test_regression.py`:
    - `test_reconciliation_dual_mismatch_and_key_handling`: Verifies dual mismatch categorization.
    - `test_full_dataset_reconciliation_from_records_json`: Verifies reconciliation against all 150 internal orders and 163 provider records in `data/records.json`, proving `ORD-1078` is present in both `amount_mismatches` and `status_mismatches`.
- **Regression Prevention:**
  Any future change that introduces an `elif` between amount and status checks or modifies amount extraction will immediately fail `test_reconciliation_dual_mismatch_and_key_handling`.

## 6. Unresolved Challenge or Next Step
- **Distributed Concurrency Considerations:**
  The current implementation is an in-memory sequential event processor. In a distributed high-throughput architecture, concurrent event delivery (e.g. two refund webhooks arriving simultaneously on separate worker nodes) would require distributed locks or database-level conditional updates (`UPDATE orders SET refunded_paise = refunded_paise + :amount WHERE refunded_paise + :amount <= refund_due_paise`) to guarantee idempotency and avoid race conditions.
