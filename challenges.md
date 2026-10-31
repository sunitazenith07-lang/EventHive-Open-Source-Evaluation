# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour

The challenge was deciding which order and payment states should allow a refund. Validating the amount was not enough on its own: the order also had to be in the right state.

## 2. Evidence

The original test suite produced:

```text
62 failed, 150 passed
```

The test that exposed the problem:

- `test_refund_eligibility_matrix`

The matrix covers orders in different states, including `PLACED`, `ACCEPTED`, `OUT_FOR_DELIVERY`, `DELIVERED`, `REJECTED`, `CANCELLED` and `FAILED`, with different payment statuses.

[FILL IN: paste the failing matrix case or assertion output you saw, if you have it.]

## 3. What I tried

1. Ran `python -m pytest -q` and `pytest -x -vv` to see the eligibility failures.
2. Examined the `refund_processed` branch of `apply_order_event()` in `service.py`.
3. First added a check that the payment status is `PAID`.
4. Re-ran the eligibility matrix. One case still failed: an order with order status `FAILED` and payment status `PAID` was still eligible.
5. Added a check that the order status is `REJECTED` or `CANCELLED`.
6. Re-ran the matrix: 12 cases passed.

## 4. Resolution

- Root cause: the refund condition did not check the payment status or the order status, so refunds could be applied to orders that were not eligible.
- What changed: the refund condition now also requires `payment_status == "PAID"` and `status in ("REJECTED", "CANCELLED")`.
- Why it addresses the cause: refunds are now applied only to paid orders in the states that create a refund due.

## 5. Proof and regression prevention

- Targeted refund eligibility matrix: 12 passed.
- Full suite after this fix: [FILL IN]
- No test files were modified.

Related cases that could still break:
- A refund event arriving after the order status changes.
- Multiple partial refunds on an eligible order.

## 6. Unresolved challenge or next step

Reconciliation status mismatch is not fixed at this commit and is handled in the next commit. An ineligible refund event is ignored, but its event ID is still recorded as processed; whether that is the intended behaviour was not investigated.