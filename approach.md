# Approach

## 1. Baseline

I started by running the current state of the project to see what's actually happening. I ran `python -m pytest -q`, and everything passed (212 tests). When I ran `python -m main`, the output showed that the reconciliation isn't perfect yet—for example, `ORD-103` is missing from the provider side and `ORD-104` is missing from our internal records. There are also some amount and status mismatches for `ORD-101` and `ORD-102`, which confirms the reconciliation logic is working as intended by flagging these gaps.

## 2. Codebase understanding

I spent time digging into how the data moves through the system. I looked at `models.py` for how orders are initialized and `service.py` for the heavy lifting. Specifically, `apply_order_event` is the core—it handles the state machine of the order (from PLACED to DELIVERED) and ensures we don't process the same event twice. `reconcile_orders` just does a dictionary comparison between two sets of data to find gaps. I verified this by stepping through the tests in `test_contract.py` and `test_acceptance_matrix.py`.

## 3. Investigation and implementation strategy

Instead of just guessing, I mapped out the most critical edge cases:
- **Idempotency**: Making sure that if we get the same event ID twice, the order doesn't change the second time.
- **Refund Limits**: Ensuring that we can't refund more money than what is actually due back to the customer.
- **Reconciliation Accuracy**: Verifying that if the status is different (even if the money is the same), it's marked as a mismatch.

## 4. Implementation decisions

Since the starter code already handles the core logic correctly, my main focus was on documenting the flow and verifying that the existing safeguards were robust. I decided to stick with the current logic because it's clean and maintainable. I assumed all money values are handled in integer paise to avoid the floating-point errors you usually get with decimals.

## 5. Verification

I kept running `python -m pytest -q` to make sure I didn't break anything. Every single test (212/212) passed. I also used the `main.py` demo to double-check that the reconciliation reports the expected mismatches for the sample data. I specifically checked the "cancellation after dispatch" case to ensure the status stays as `OUT_FOR_DELIVERY`.
