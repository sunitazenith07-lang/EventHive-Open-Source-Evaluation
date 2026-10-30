# Challenges

## 1. Challenge or confusing behaviour

The trickiest part for me was reasoning about how cumulative refunds work. It's easy to think of a refund as a single event, but in the real world, a customer might get a partial refund first and then another one later. I had to make sure the code didn't just check the latest refund against the total, but tracked the *sum* of all refunds given so far.

## 2. Evidence

I looked at `tests/test_contract.py` and found `test_refund_cannot_exceed_amount_due`. It specifically checks that if you try to refund 1200 paise when only 1000 is due, it gets rejected. I also noticed `test_partial_refund_is_not_marked_complete`, which proves that a partial refund keeps the order status as `PAID` rather than jumping straight to `REFUNDED`.

## 3. What I tried

To wrap my head around this, I did three things:
- I traced the `if` conditions in `service.py` to see exactly when a refund is allowed (it has to be a PAID order and either CANCELLED or REJECTED).
- I compared the different refund scenarios in the acceptance matrix tests to see how they handle bad inputs like strings or floats instead of integers.
- I ran the test suite multiple times to confirm that the current logic already handles these edge cases without crashing.

## 4. Resolution

The logic in the code is actually quite solid: it checks `refund_due_paise - refunded_paise` to find the remaining balance. It only marks the order as `REFUNDED` once that balance hits zero. This prevents the "over-refund" bug. I didn't need to change the code because the existing implementation already follows this guardrail.

## 5. Proof and regression prevention

The tests `test_refunds_cannot_exceed_due` and `test_valid_partial_and_full_refunds` act as the safety net here. They ensure that no matter how many partial refunds happen, the total never exceeds the original order amount. There's also `test_invalid_refund_amounts_are_ignored` which handles the "garbage" input (like `None` or booleans), so the system doesn't crash on bad data.

## 6. Unresolved challenge or next step

One thing this system doesn't handle is concurrency. Since it uses simple Python dictionaries in memory, if two refund requests hit the server at the exact same millisecond, you could theoretically have a race condition. If I were to take this further, I'd look into using a database with atomic transactions to lock the order record during a refund.
