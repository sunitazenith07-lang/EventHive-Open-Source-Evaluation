# ORDER_FLOW_NOTES.md — Required submission

Complete this file with your own actual examples and results. Do not leave prompts unanswered.

## 1. Example order-event sequence
Order `ORD-201`, total 1000 paise: paid, rejected, then refunded in two parts. State = order status / payment status / refund due / refunded.

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `payment_confirmed` | `PLACED` / `PAID` / 0 / 0 | Matches |
| 2 | `restaurant_rejected` | `REJECTED` / `PAID` / 1000 / 0 | Matches |
| 3 | `refund_processed`, `amount_paise` 400 | `REJECTED` / `PAID` / 1000 / 400 | Matches |
| 4 | `refund_processed`, `amount_paise` 600 | `REJECTED` / `REFUNDED` / 1000 / 1000 | Matches |

Evidence: `test_ord_201_example_sequence` asserts the state after each step and passed in the final suite (226 passed).

## 2. Three edge cases
1. **Refund over the balance:** refund 400, then 601 on a 1000 due. Expected: the 601 refund is ignored. Actual: `refunded_paise` stayed 400. Test: `test_refund_one_paisa_over_remaining_is_ignored`.
2. **Replayed refund:** refund 400 with ID `r1`, then `r1` again. Expected: not applied twice. Actual: `refunded_paise` was 400. Test: `test_refund_replay_same_event_id_not_applied_twice`.
3. **Cancel after dispatch:** `restaurant_accepted`, `dispatch_started`, `cancel_requested`. Expected: cancel ignored. Actual: status stayed `OUT_FOR_DELIVERY`. Test: `test_cancel_after_dispatch_is_ignored`.

## 3. Assumptions and limitations
- Cancellation is accepted only in `PLACED` or `ACCEPTED`; after dispatch it is ignored.
- Transitions: `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`; rejection only from `PLACED`.
- A paid order that is rejected or cancelled gets refund due equal to its full total.
- Refunds are integer paise, need `PAID` payment and `REJECTED`/`CANCELLED` order, and cannot exceed `refund_due_paise - refunded_paise`.
- A partial refund keeps `PAID`; payment becomes `REFUNDED` when the refunded total reaches the due amount.
- Unresolved: events without `event_id` after the first are treated as duplicates; an invalid refund still records its event ID; reconciliation reports only the amount mismatch when both differ.