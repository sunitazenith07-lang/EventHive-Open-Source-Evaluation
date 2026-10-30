# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
Two subtle issues stood out during investigation:
1. **Schema asymmetry and simultaneous mismatches in `reconcile_orders`:** Running `python -m main` on the starter code reported `amount_mismatches: ['ORD-101', 'ORD-102']` and `matched: []`, even though `fixtures.py` defined `ORD-101` with `45900` paise on both sides and `ORD-102` with `129900` paise on both sides. At the same time, `data/records.json` listed `"amount and status mismatches individually and together"` as a required edge case.
2. **Python boolean subclass trap in refund validation:** In `test_invalid_refund_amounts_are_ignored`, passing `amount_paise=True` was accepted as a valid `1` paise refund by standard `isinstance(amount, int)` checks.

## 2. Evidence
- **Evidence 1 (`main.py` & `fixtures.py` vs `test_acceptance_matrix.py`):**
  - `models.new_order("ORD-101", 45900)` creates `{"order_id": "ORD-101", "total_paise": 45900, ...}`.
  - `sample_provider_orders()` creates `{"order_id": "ORD-101", "amount_paise": 45900, "status": "PLACED"}`.
  - In starter `service.py`, `a.get("amount_paise") != b.get("amount_paise")` evaluated `None != 45900`, falsely flagging `ORD-101` and `ORD-102` as `amount_mismatches` and masking that `ORD-102` (`ACCEPTED` vs `CANCELLED`) was actually a `status_mismatch`.
- **Evidence 2 (`pytest -v` output on `test_invalid_refund_amounts_are_ignored[True]`):**
  - `AssertionError: assert 1 == 0` when `amount_paise=True` was passed to `refund_processed`, because `bool` subclasses `int` in Python (`isinstance(True, int) == True` and `True > 0`).

## 3. What I tried
1. Initially, I inspected how `test_acceptance_matrix.py` called `reconcile_orders`: the test passed `{"order_id": "O", "amount_paise": 5000, "status": left}` for both `internal` and `provider`. When I inspected `fixtures.py` and `data/records.json`, however, all 150 internal orders used `"total_paise"` while the 163 provider records used `"amount_paise"`.
2. I also tested what happened in `reconcile_orders` if I simply replaced `else:` with `elif a.get("status") != b.get("status"):`. When an order had *both* a different amount and a different status, `elif` reported the order only in `amount_mismatches` and omitted it from `status_mismatches`, violating Requirement 6 ("Report missing records, amount mismatches and status mismatches separately and deterministically") and the `data/records.json` edge case `"amount and status mismatches individually and together"`.

## 4. Resolution
1. **Amount extraction helper & independent mismatch checks:** In `reconcile_orders`, I implemented `_get_amount(r)` to check `r.get("amount_paise") if "amount_paise" in r else r.get("total_paise")`. I then decoupled the amount and status checks into independent `if amt_mismatch:` and `if status_mismatch:` branches, appending to `matched` only when `not amt_mismatch and not status_mismatch`.
2. **Strict integer helper:** I implemented `_is_strict_int(val)` returning `isinstance(val, int) and not isinstance(val, bool)` and applied it to all paise validations (`amount_paise`, `total_paise`, `refund_due_paise`, and `refunded_paise`).

## 5. Proof and regression prevention
- Verified via `python -m main`, which now outputs `matched: ['ORD-101']` and `status_mismatches: ['ORD-102']`.
- Added `test_reconcile_handles_total_paise_and_simultaneous_amount_and_status_mismatch` and `test_boolean_and_non_integer_refund_amounts_rejected` in `tests/test_contract.py`, plus `test_records_json_dataset_reconciliation_and_events_smoke` over all 150 internal orders, 163 provider records, and 219 events. All 220 tests pass (`python -m pytest -q`).

## 6. Unresolved challenge or next step
- Duplicate `order_id` entries within the same input list (`internal` or `provider`) currently keep the last seen dictionary when keyed by `order_id`. A future enhancement would explicitly report duplicate primary keys within a single source list as a separate data-integrity anomaly.
