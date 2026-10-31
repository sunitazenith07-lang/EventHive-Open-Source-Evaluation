# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour

The challenge was deciding what counts as a valid refund amount. Checking the type and sign was not enough: a refund also must not push the refunded total past the refund due, so the check has to use the remaining balance, not just the amount.

## 2. Evidence

The original test suite produced:

```text
62 failed, 150 passed
```

Tests that exposed the problem:

- `test_invalid_refund_amounts_are_ignored`
- `test_valid_partial_and_full_refunds`
- `test_refunds_cannot_exceed_due`

These tests cover invalid values such as zero, negative numbers, booleans, non-integer values, and amounts greater than the refund due.

[FILL IN: paste the assertion error or failing output for one of these tests before the fix, if you have it.]

## 3. What I tried

1. Ran `python -m pytest -q` and `pytest -x -vv` to see the refund failures.
2. Examined the `refund_processed` branch of `apply_order_event()` in `service.py`.
3. First added validation for the amount type (integer, not boolean) and a positive value.
4. Further test failures showed that amounts larger than the remaining refund were still accepted, so I added a remaining-balance check: `amount <= refund_due_paise - refunded_paise`.
5. Kept the `REFUNDED` payment status update so it only happens when the refunded total reaches the refund due.
6. Re-ran the refund tests.

## 4. Resolution

- Root cause: the refund branch did not sufficiently validate the amount before adding it to `refunded_paise`.
- What changed: the refund is now applied only when the amount is a positive integer (not a boolean) and does not exceed the remaining refund due.
- Why it addresses the cause: invalid and excessive amounts no longer change `refunded_paise`, and the refunded total can never go above the refund due.

## 5. Proof and regression prevention

- Targeted refund tests: [FILL IN]
- Full suite after this fix: [FILL IN]
- No test files were modified.

Related cases that could still break:
- Several partial refunds that together reach the exact refund due.
- A refund event for an order that is not eligible for a refund (not yet fixed at this commit).

## 6. Unresolved challenge or next step

Refund eligibility (payment status and order status) is not checked at this commit and is handled in the next commit. An invalid refund event is ignored, but its event ID is still recorded as processed; whether that is the intended behaviour was not investigated.