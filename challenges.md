# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The most confusing bug I encountered was during refund amount validation. In my initial fix, I wrote:
```python
if isinstance(amount, int) and amount > 0:
```
I thought this was enough to ensure that only valid integers would be processed. But when running the tests, `test_invalid_refund_amounts_are_ignored[True]` kept failing with:
`assert 1 == 0`
The order had its `refunded_paise` set to 1 instead of staying 0. It was confusing at first because `True` is a boolean, not an integer, so I didn't expect it to pass `isinstance(..., int)`.

Another tricky thing was the demo in `main.py`. Both `ORD-101` and `ORD-102` were showing up as amount mismatches even though their amounts were the exact same (45900 and 129900).

---

## 2. Evidence
Here is the pytest error when using `isinstance`:
```text
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
order = {'order_id': 'O', 'payment_status': 'PAID', 'processed_event_ids': ['R'], 'refund_due_paise': 5000, ...}
amount = True

    @pytest.mark.parametrize("amount", [0, -1, -10, 0.5, True, None, "10", [], {}, 5001, 6000, 10000, -5000, 2.2, False])
    def test_invalid_refund_amounts_are_ignored(amount):
...
>       assert result["refunded_paise"] == 0
E       AssertionError: assert 1 == 0
```
For `main.py`, running the baseline showed:
```text
amount_mismatches: ['ORD-101', 'ORD-102']
```
even though in `fixtures.py`, `ORD-101` had `total_paise: 45900` in `sample_orders()` and `amount_paise: 45900` in `sample_provider_orders()`.

---

## 3. What I tried
1. **For the boolean refund issue:**
   I tested the behavior in the Python REPL:
   ```python
   >>> isinstance(True, int)
   True
   >>> issubclass(bool, int)
   True
   >>> type(True) is int
   False
   >>> type(100) is int
   True
   ```
   I realized that in Python, `bool` is actually a subclass of `int`. Because of this inheritance, `isinstance(True, int)` evaluates to `True`, and in numeric operations `True` acts as `1`.

2. **For the amount mismatch in `main.py`:**
   I inspected `fixtures.py` and `models.py`. Internal orders created by `new_order()` use the key `"total_paise"`, while provider orders use `"amount_paise"`. In `service.py`, the starter code did:
   ```python
   if a.get("amount_paise") != b.get("amount_paise"):
   ```
   Because `a` only had `"total_paise"`, `a.get("amount_paise")` returned `None`, which triggered `None != 45900`.

---

## 4. Resolution
1. **Strict integer check:**
   I updated the refund validation in `service.py` to use `type(amount) is int`:
   ```python
   if type(amount) is int and amount > 0 and amount <= remaining:
       out["refunded_paise"] += amount
   ```
   Because `type(True)` is `bool` (not `int`), this check cleanly filters out `True` and `False` without needing extra boolean checks. It also rejects floats, strings, and other non-integers.

2. **Handling both key names in reconciliation:**
   I modified `reconcile_orders` to check for both keys:
   ```python
   a_amount = a.get("amount_paise") if "amount_paise" in a else a.get("total_paise")
   b_amount = b.get("amount_paise") if "amount_paise" in b else b.get("total_paise")
   ```
   This immediately fixed `ORD-101` in `main.py` so it correctly shows as `matched`.

---

## 5. Proof and regression prevention
- `pytest tests/test_acceptance_matrix.py -k test_invalid_refund_amounts_are_ignored` now passes for all 15 cases.
- Added `test_boolean_refund_amount_rejected()` in `tests/test_regression_and_edge_cases.py` to explicitly test `True`, `False`, `100.5`, `"500"`, `None`, and dicts/lists.
- `python -m main` now reports:
  ```text
  matched: ['ORD-101']
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: []
  status_mismatches: ['ORD-102']
  ```

---

## 6. Unresolved challenge or next step
- **Race conditions with concurrent events:**
  Currently the code assumes events are processed one after another in a single thread. In a real-world platform, webhooks from Razorpay or Stripe and updates from delivery partners happen concurrently. If two webhooks arrive at the same time for the same order, in-memory checks won't stop race conditions. To handle this in production, we would need database row-level locking or distributed locks (like Redis) keyed on `order_id`.
