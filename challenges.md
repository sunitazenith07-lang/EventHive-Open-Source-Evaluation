# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The primary subtle challenge involved two coupled edge cases:
1. **Python boolean-as-integer edge case in refund validation:** In Python, `bool` is a subclass of `int` (`issubclass(bool, int) is True`). Using standard `isinstance(amount, int)` allowed boolean values like `True` to evaluate as integer `1`, corrupting the monetary ledger (`refunded_paise += 1`).
2. **Key divergence between internal orders and reconciliation records:** The `new_order` generator in `models.py` produces records with `total_paise`, whereas provider records and test fixtures in `test_contract.py` pass dictionaries with `amount_paise`. This caused `python -m main` to falsely report amount mismatches for completely matching orders.
3. **Simultaneous multi-attribute reconciliation mismatches:** When an order differs in both monetary amount and order state, deciding whether it should appear in `amount_mismatches`, `status_mismatches`, or both.

## 2. Evidence
- **Boolean refund amount test failure:**
  Running `pytest` against `test_invalid_refund_amounts_are_ignored[True]` yielded:
  ```text
  tests/test_acceptance_matrix.py:68: in test_invalid_refund_amounts_are_ignored
      assert result["refunded_paise"] == 0
  E   AssertionError: assert 1 == 0
  ```
- **Demo mismatch output:**
  Running `python -m main` on untouched fixtures produced:
  ```text
  amount_mismatches: ['ORD-101', 'ORD-102']
  ```
  Even though `ORD-101` had `total_paise: 45900` internally and `amount_paise: 45900` from provider.
- **Edge-case catalog definition:**
  In `data/records.json`, edge case 10 explicitly mandates handling:
  `"amount and status mismatches individually and together"`.

## 3. What I tried
1. For refund types, initially tested `isinstance(amount, int)`, which passed tests for strings, floats, and objects, but failed for `True`. Tested using `type(amount) is int`, which strictly accepts `int` and excludes `bool`.
2. For reconciliation key divergence, inspected `data/records.json` and `fixtures.py`. Confirmed that internal order records use `total_paise` while external/provider records use `amount_paise`. Tested creating an extraction helper `_extract_amount(r)` that checks `"amount_paise" in r` first, falling back to `r.get("total_paise")`.
3. For multi-dimension mismatches, evaluated using an `if / elif` vs two independent `if` statements. The `if / elif` approach caused status mismatches to be hidden when amounts also differed. Two independent checks correctly populated both reporting lists while excluding the order from `matched`.

## 4. Resolution
- **Exact type checking for currency:** Replaced loose numeric checks with:
  ```python
  is_valid_amount = (
      type(amount) is int
      and amount > 0
      and (out.get("refunded_paise", 0) + amount) <= out.get("refund_due_paise", 0)
  )
  ```
  This guarantees that negative amounts, zero, floats (`0.5`), booleans (`True`), and excess amounts are safely rejected.
- **Unified amount extractor:** Implemented:
  ```python
  def _extract_amount(r):
      if not isinstance(r, dict):
          return None
      if "amount_paise" in r:
          return r["amount_paise"]
      return r.get("total_paise")
  ```
- **Independent mismatch tracking:** Used separate conditions:
  ```python
  amount_match = (amount_a == amount_b)
  status_match = (status_a == status_b)

  if not amount_match:
      report["amount_mismatches"].append(key)
  if not status_match:
      report["status_mismatches"].append(key)
  if amount_match and status_match:
      report["matched"].append(key)
  ```

## 5. Proof and regression prevention
- `test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored` now passes across all 15 parametrized values, including `True`, `False`, `None`, and negative values.
- `tests/test_regression.py::test_reconciliation_simultaneous_amount_and_status_mismatch` specifically asserts that when both amount and status mismatch, the order ID is present in both discrepancy lists and absent from `matched`.
- `main.py` now runs and properly categorizes `ORD-101` in `matched` and `ORD-102` in `status_mismatches`.

## 6. Unresolved challenge or next step
- In high-throughput distributed systems, events might arrive severely delayed or out of order across separate threads. While our implementation cleanly handles out-of-order `payment_confirmed` following rejection/cancellation, handling complex distributed races in a production deployment would require distributed locking, transactional database boundaries, or event sourcing with vector clocks.
