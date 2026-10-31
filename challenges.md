# challenges.md — Challenges and Debugging (Compulsory)

## 1. Challenge or confusing behaviour
The most intricate behavior encountered was handling edge cases around refund processing, specifically differentiating between strict integer types in Python (where boolean values like `True` and `False` are subclasses of `int`) and preventing cumulative refunds from exceeding the outstanding `refund_due_paise` boundary across multiple partial refund events.

## 2. Evidence
- **Test Failure Assertions:** 
  - `AssertionError: assert 5001 == 2500` (when testing cumulative refunds exceeding the due amount).
  - `AssertionError: assert 1 == 0` (when testing boolean `True` passed as an invalid refund amount).
- **Traceback example:** 
  `TypeError: unsupported operand type(s) for +=: 'int' and 'NoneType'` when `amount_paise` was `None`.

## 3. What I tried
1. **Attempt 1 (Basic type check):** Checked `if isinstance(amount, int):` which initially failed because `isinstance(True, int)` evaluates to `True` in Python, causing boolean values to pass as valid integer paise amounts.
2. **Attempt 2 (Explicit type and range restriction):** Switched to strict type identity checking `type(amount) is int and not isinstance(amount, bool)` combined with `amount > 0` and cumulative boundary checks (`current_refunded + amount <= refund_due`).

## 4. Resolution
- **Root Cause:** Python's type hierarchy treats `bool` as a subclass of `int`, and missing boundary validation allowed invalid or out-of-bounds partial refunds to bypass sanity checks.
- **Change Made:** Enforced strict type checking (`type(amount) is int`), positive sign checks, and pre-addition boundary assertions inside the `refund_processed` event handler in `service.py`. This addressed the root cause by sanitizing input payloads at the domain boundary rather than masking errors downstream.

## 5. Proof and regression prevention
- **Demonstrating Tests:** Validated via `tests/test_acceptance_matrix.py` (specifically `test_invalid_refund_amounts_are_ignored`, `test_refunds_cannot_exceed_due`, and `test_refund_eligibility_matrix`).
- **Potential Breaking Edge Case:** Concurrent refund processing requests arriving simultaneously for the same order ID could cause race conditions if external thread safety isn't managed.

## 6. Unresolved challenge or next step
- **Limitation:** The current synchronous service layer relies on in-memory dictionary mutations without distributed locking or persistent transaction isolation.
- **Next Step:** Introduce thread locks (`threading.Lock`) or transactional state wrappers if scaling this event processor to handle concurrent multi-threaded API requests.