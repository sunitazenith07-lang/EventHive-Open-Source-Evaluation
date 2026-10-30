# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour

The most challenging part was understanding the refund processing logic, especially how multiple partial refund events should update an order.

Initially, partial refunds changed the payment status to `PARTIALLY_REFUNDED`. This caused later valid refund events to be rejected.

## 2. Evidence

The initial test run showed:

- 189 tests passed.
- 23 tests failed.

One failure was:

`test_partial_refund_is_not_marked_complete`

The expected payment status after a partial refund was `PAID`, but the implementation returned `PARTIALLY_REFUNDED`.

Other failures showed that the second refund amount was not being added to the previously refunded amount.

## 3. What I tried

- Ran `python -m pytest -q` to identify failing tests.
- Read the failure messages to understand the expected behaviour.
- Used PowerShell `Select-String` to locate `PARTIALLY_REFUNDED` in `service.py`.
- Inspected the refund-processing condition.
- Removed the partial-refund status assignment while keeping the full-refund status update.
- Saved the file and ran the tests again.

## 4. Resolution

The root cause was that the payment status changed after a partial refund. The eligibility condition for the next refund required the payment status to be `PAID`.

I changed the logic so that the payment status remains `PAID` while the refund is partial. It changes to `REFUNDED` only when the complete refund amount has been processed.

This fixed the underlying state-transition issue instead of bypassing the tests.

## 5. Proof and regression prevention

The final test command was:

`python -m pytest -q`

Actual result:

`212 passed in 0.26s`

The visible tests covered partial refunds, full refunds, multiple refund events, and refund amounts that could exceed the amount due.

These tests help prevent the same refund-processing issue from returning.

## 6. Unresolved challenge or next step

All 212 visible tests passed. Hidden tests and additional edge cases have not yet been verified.

A useful next step would be to test duplicate refund event IDs, invalid refund amounts, and unusual event sequences to check the robustness of the implementation.