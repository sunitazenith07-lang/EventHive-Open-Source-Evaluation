# ORDER_FLOW_NOTES.md — Required submission

## 1. Example order-event sequence
Starting order: `new_order("O1", 5000)` (`status="PLACED"`, `payment_status="UNPAID"`, `refund_due_paise=0`, `refunded_paise=0`).

| Step | Event | Expected order/payment/refund state | Actual result |
|---|---|---|---|
| 1 | `{"event_id": "e1", "type": "payment_confirmed"}` | `PLACED`, `PAID`, due=`0`, refunded=`0` | `PLACED`, `PAID`, due=`0`, refunded=`0` |
| 2 | `{"event_id": "e2", "type": "restaurant_accepted"}` | `ACCEPTED`, `PAID`, due=`0`, refunded=`0` | `ACCEPTED`, `PAID`, due=`0`, refunded=`0` |
| 3 | `{"event_id": "e3", "type": "cancel_requested"}` | `CANCELLED`, `PAID`, due=`5000`, refunded=`0` | `CANCELLED`, `PAID`, due=`5000`, refunded=`0` |
| 4 | `{"event_id": "e4", "type": "refund_processed", "amount_paise": 2000}` | `CANCELLED`, `PAID`, due=`5000`, refunded=`2000` | `CANCELLED`, `PAID`, due=`5000`, refunded=`2000` |
| 5 | `{"event_id": "e5", "type": "refund_processed", "amount_paise": 3000}` | `CANCELLED`, `REFUNDED`, due=`5000`, refunded=`5000` | `CANCELLED`, `REFUNDED`, due=`5000`, refunded=`5000` |

## 2. Three edge cases
1. **Duplicate refund event:**
   - *Input:* Send `{"event_id": "r1", "type": "refund_processed", "amount_paise": 2000}` twice on a cancelled paid order (due `5000`).
   - *Expected:* Refund is applied once (`refunded_paise=2000`) and `"r1"` appears once in `processed_event_ids`.
   - *Actual:* `refunded_paise == 2000`, `processed_event_ids == ["r1"]`.
   - *Test:* `test_idempotent_refund_replay_does_not_duplicate_refund` in `tests/test_regression.py`.
2. **Cancel requested after dispatch:**
   - *Input:* Order moves `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY`, then receives `cancel_requested`.
   - *Expected:* Cancellation is ignored; status remains `OUT_FOR_DELIVERY` and `refund_due_paise` stays `0`.
   - *Actual:* `status == "OUT_FOR_DELIVERY"`, `refund_due_paise == 0`.
   - *Test:* `test_cancel_after_dispatch_is_safely_ignored` in `tests/test_regression.py`.
3. **Partial refund followed by an over-refund:**
   - *Input:* Order has `refund_due_paise=6000`. First refund is `2500`, second refund is `4000`.
   - *Expected:* First refund succeeds (`refunded_paise=2500`), second is ignored because `2500 + 4000 > 6000`. Status stays `PAID`.
   - *Actual:* `refunded_paise == 2500`, `payment_status == "PAID"`.
   - *Test:* `test_refund_exact_split_to_full` in `tests/test_regression.py`.

## 3. Assumptions and limitations
- Orders can only be cancelled when `PLACED` or `ACCEPTED`, and rejected only when `PLACED`.
- Refunds are only valid for `REJECTED` or `CANCELLED` orders with `payment_status == "PAID"` and `refund_due_paise > 0`.
- All amounts must be positive integers in paise.
- Limitation: state is stored in plain Python dicts in memory without concurrency locking.
