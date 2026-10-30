# Approach — OrderOps

## Baseline and environment
- Python 3.11 on Windows, using VS Code and PowerShell.
- Command: `python -m pytest -q`.
- Initial reported result: **150 passed, 62 failed, 1 warning**. After a local duplicate-event guard was added, a later run reported **171 passed, 41 failed, 1 warning**.
- On branch `fix/order-event-refund-reconciliation`, the observed result was **212 passed, 1 warning** (twice, in 0.84s and 0.94s).
- The warning originates from the installed `anyio` pytest plugin's use of a deprecated `CallSpec2` alias; it is not a failing application test.

## Codebase and data flow
- `models.new_order` creates an order with status, payment status, refund counters, and processed event IDs.
- `service.apply_order_event` deep-copies the input, applies an order/payment/refund event, and records event IDs.
- `service.reconcile_orders` compares internal and provider order summaries by ID.
- `main.py` runs the synthetic demo.
- Visible tests include transition matrices, refund constraints, replay idempotency, deterministic reconciliation, and input immutability.

## Defects investigated and corrections
1. **Duplicate delivery of events:** The original code appended the same event ID repeatedly. The revised logic checks previously processed IDs before any state update.
2. **Refund amount safety:** The original implementation directly added `amount_paise`, allowing negatives, floats, booleans, excess amounts, and exceptions on invalid types. The fix accepts only a positive integer amount within the outstanding refundable balance.
3. **Refund eligibility:** The original code could refund an unpaid or active order. The fix requires a paid order in `CANCELLED` or `REJECTED` status with a positive refund due.
4. **Partial versus full refunds:** A successful partial refund stays `PAID`; only reaching the exact refund due marks payment `REFUNDED`.
5. **Reconciliation:** The original function checked amount differences but could classify different statuses as matched. The revision reports amount and status differences independently and treats records as matched only if both agree.

## Decisions and limitations
- The service continues to return a deep-copied order to avoid mutating the caller's input.
- The refund amount uses `type(amount) is int`, so Python booleans are not accidentally counted as paise.
- Refunds that would exceed the remaining balance are rejected rather than silently capped.
- The implementation retains the existing public function signatures and report categories.
- The repository's AI-use requirements should be clarified with the evaluator; assistance was used to produce code and these notes and must not be misrepresented as independent work.

## Verification
- `python -m pytest -q`: **212 passed, 1 warning**.
- `python -m main`: produced reconciliation lists for order IDs `ORD-101` through `ORD-104`.
- `git status`: working tree clean after switching to the fix branch.
- These are visible/local checks only; passing them does not establish that all hidden or future edge cases pass.
