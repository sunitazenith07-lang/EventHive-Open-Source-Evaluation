# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The trickiest part was figuring out why certain invalid refund tests (like passing `amount_paise=True`) were failing. In Python, booleans are a subtype of integers (`True` equals `1`), so standard `isinstance(True, int)` checks returned true and incorrectly processed a 1-paise refund.

## 2. Evidence
When running `pytest`, the test checking for invalid refund types failed because `amount_paise=True` bypassed the integer validation check and credited 1 paise to the order.

## 3. What I tried
- Tried checking `type(amount_paise) == int`, which still let booleans through because of Python's inheritance rules.
- Tested explicit boolean filtering.

## 4. Resolution
Added an explicit check `and not isinstance(amount_paise, bool)` alongside the integer check. This successfully blocked booleans from being treated as money without hiding any underlying symptoms.

## 5. Proof and regression prevention
Demonstrated by `test_invalid_refund_amounts_are_ignored` in the test suite, which passes all edge-case non-integer and boolean inputs correctly.

## 6. Unresolved challenge or next step
None encountered for this scope. Next steps would involve adding database persistence layer integration if scaled to production.