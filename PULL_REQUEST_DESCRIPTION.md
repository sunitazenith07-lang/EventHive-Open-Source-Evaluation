# Pull Request Title
```text
Fix order lifecycle events, refund validation, and reconciliation mismatches
```

---

# Pull Request Description

## What did you change?
I fixed several bugs across `apply_order_event` and `reconcile_orders` in `service.py`:
- Added duplicate event protection so re-sending the same `event_id` doesn't run the logic again or add duplicate IDs.
- Fixed refund validation: only paid orders that are cancelled or rejected can receive refunds, amounts must be positive integers, and refunds cannot exceed the remaining balance.
- Handled late payments: if payment confirmation arrives after a cancellation or rejection, `refund_due_paise` is now correctly set to the order total.
- Fixed reconciliation: checked both amount and status between internal and provider records, and handled cases where internal records use `total_paise` while provider records use `amount_paise`.
- Added 8 regression tests in `tests/test_regression.py` covering edge cases.
- Completed all required notes files (`approach.md`, `challenges.md`, `optimizations.md`, `TESTING.md`, `ORDER_FLOW_NOTES.md`).

## Root cause
1. **Duplicate events**: `apply_order_event` was appending every `event_id` straight to `processed_event_ids` without checking if it was already processed.
2. **Refund bugs**: The starter code didn't check order status or payment status before refunding. It also accepted negative numbers, floats, and booleans (`True` in Python is treated like 1). On new unpaid orders, `refund_due_paise` was 0, so `0 >= 0` evaluated to True and prematurely marked them as `REFUNDED`.
3. **Reconciliation bug**: In `reconcile_orders`, the code only compared amounts. If the amount matched, it called the order "matched" even if the statuses were different. Also, internal orders created with `new_order` use `total_paise`, but the function only looked for `amount_paise`, causing false amount mismatches in the demo.

## Tests
- [x] I ran `python -m pytest -q`.
- [x] I added or updated regression tests for my change.
- [x] I did not delete, skip, weaken or bypass existing tests.

**Test Results:**
- Baseline before fix: 62 failed, 150 passed (212 tests total).
- After fix: **220 passed, 0 failed in 0.30s**.
- Offline demo (`python -m main`) output:
  - `matched: ['ORD-101']`
  - `missing_from_provider: ['ORD-103']`
  - `missing_from_internal: ['ORD-104']`
  - `amount_mismatches: []`
  - `status_mismatches: ['ORD-102']`

## Required problem-solving documents (all three mandatory; 15 marks total)
- [x] `approach.md` completed (5 marks) - Traced the test failures, outlined the state machine changes, and kept functions pure by deepcopying input orders.
- [x] `challenges.md` completed (COMPULSORY; 5 marks) - Detailed the tricky Python issue where `isinstance(True, int)` is True, resolving `total_paise` vs `amount_paise`, and fixing late payment confirmation.
- [x] `optimizations.md` completed (5 marks) - Explained returning early when duplicate event IDs are spotted and why keeping `processed_event_ids` as a list is better for serializing order history.

## Edge cases checked
1. **Duplicate payment event**: Replayed `payment_confirmed` with event ID `EVT-100`; it kept `payment_status: PAID` and only kept one `EVT-100` in `processed_event_ids`.
2. **Boolean refund amount**: Sent `amount_paise=True`; it was rejected and `refunded_paise` stayed 0.
3. **Excess refund attempt**: On a 3,000 paise order with 1,000 already refunded, tried refunding 2,500 paise. The event was ignored and refunded amount stayed 1,000 paise.
4. **Late payment**: Order was cancelled while unpaid, then `payment_confirmed` arrived later. `refund_due_paise` properly updated to the order total.
5. **Cancel after dispatch**: Sent `cancel_requested` for an order in `OUT_FOR_DELIVERY`; the status stayed `OUT_FOR_DELIVERY`.

## Design decisions / limitations
- I kept `processed_event_ids` as a regular list so it stays JSON-serializable and preserves the exact order in which events happened.
- Used `type(amount) is int` rather than `isinstance` to strictly keep booleans out of currency amounts.
- In distributed environments, if a refund arrives before payment is even confirmed, it currently gets rejected as unpaid. In production, that would need a retry queue.

## Integrity confirmation
- [x] This is my own individual work.
- [x] I have followed the evaluation's AI-use policy.
- [x] I can explain my changes and make a small live modification if asked.
