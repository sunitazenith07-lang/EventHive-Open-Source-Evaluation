# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The most intricate challenge was handling refund amount validation against Python's type hierarchy while safeguarding financial bounds.
Specifically:
1. In Python, `bool` is a subclass of `int` (`isinstance(True, int) == True`). When writing `isinstance(amount, int)`, values like `True` and `False` passed the check, evaluating as 1 paise and 0 paise respectively.
2. In the reconciliation logic, internal orders initialized via `new_order()` use `total_paise`, whereas external provider records use `amount_paise`. Direct lookups against `amount_paise` caused false amount mismatches even when values were identical.
3. Ensuring that late-arriving events (such as `payment_confirmed` arriving after an order was already `CANCELLED` or `REJECTED`) properly set `refund_due_paise` without prematurely marking the order as `REFUNDED`.

## 2. Evidence
- Python Type Assertion Failure:
  When using `isinstance(amount, int) and amount > 0`:
  `test_invalid_refund_amounts_are_ignored[True]` failed because `True` was treated as integer `1` and refunded.
- Demo False Mismatches:
  Running `python -m main` produced:
  `amount_mismatches: ['ORD-101', 'ORD-102']`
  Inspecting `fixtures.py` revealed `sample_orders()` has `total_paise: 45900`, whereas `sample_provider_orders()` has `amount_paise: 45900`.
- Matrix Reconciliation Failures:
  `test_reconciliation_status_mismatch_matrix[PLACED-ACCEPTED]` failed because the starter code had an unverified `else: report["matched"].append(key)`.

## 3. What I tried
- For the type validation bug:
  - First attempt: `isinstance(amount, int) and amount > 0`. Observed that `True` passed as valid.
  - Second attempt: Explicitly checked `type(amount) is int and amount > 0`. This strictly ensures only genuine integer types are accepted and rejects boolean instances (`bool`), floats (`float`), strings, and `None`.
- For the reconciliation field discrepancy:
  - Inspected the dictionary structure in `models.py`, `fixtures.py`, and `data/records.json`.
  - Added key fallback: `a_amount = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")`.
- For status mismatches:
  - Evaluated status differences independently of amount differences using a flag `has_mismatch`. If both amount and status differ on the same order ID, it is reported under both categories, and excluded from `matched`.

## 4. Resolution
- Replaced loose type checking with exact type identity: `type(amount) is int and amount > 0`.
- Checked order eligibility: `out.get("status") in ("REJECTED", "CANCELLED") and out.get("payment_status") == "PAID"`.
- Enforced outstanding due constraint: `amount <= (out.get("refund_due_paise", 0) - out.get("refunded_paise", 0))`.
- Only transitioned `payment_status` to `"REFUNDED"` when cumulative `refunded_paise` equals `refund_due_paise`.
- Harmonized reconciliation keys between `total_paise` and `amount_paise`.

## 5. Proof and regression prevention
- Ran the full test suite:
  - `test_invalid_refund_amounts_are_ignored` parameterized across 15 invalid types (including `True`, `False`, `0.5`, `None`, negative integers, and excessive values) passed.
  - `test_refunds_cannot_exceed_due` across 20 distinct combinations passed.
  - `test_reconciliation_status_mismatch_matrix` across all 12 status pairs passed.
- No regression in existing contracts or acceptance tests.

## 6. Unresolved challenge or next step
- Out-of-order event streams: Currently, if a `refund_processed` event arrives before `payment_confirmed` or before cancellation, it is ignored due to order eligibility guards. In an asynchronous event stream with eventual consistency, holding ineligible refund events in an unapplied retry buffer until prerequisite events arrive would be a valuable architectural enhancement.
