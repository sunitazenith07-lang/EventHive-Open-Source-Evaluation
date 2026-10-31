# OrderOps Architecture Notes

## Source file map
- **`service.py`**:
  - `apply_order_event(order: dict, event: dict) -> dict`: Implements the order lifecycle state machine, event deduplication/idempotency, and safe refund accounting in integer paise.
  - `reconcile_orders(internal: list[dict], provider: list[dict]) -> dict`: High-performance deterministic reconciler indexing records by `order_id` in $O(N + M)$ time.
  - `summarize_orders_by_state(orders: list[dict]) -> dict[str, int]`: Operational stretch feature aggregating order counts across lifecycle states.
- **`models.py`**:
  - `new_order(order_id, total_paise, status="PLACED")`: Factory returning initialized order dictionaries conforming to internal schema.
- **`fixtures.py` & `main.py`**:
  - Offline demo fixtures and execution harness comparing sample internal orders against simulated provider records.
- **`tests/test_acceptance_matrix.py`**:
  - Matrix validation tests for status transitions, idempotency, refund eligibility, and reconciliation.
- **`tests/test_contract.py`**:
  - Acceptance contract regression suite.
- **`tests/test_regression_and_edge_cases.py`**:
  - Supplemental regression suite covering boundary cases, type coercion pitfalls, dual mismatches, and aggregation.
- **`data/records.json`**:
  - Synthetic dataset comprising 150 internal orders, 163 provider records, 219 event examples, and edge-case anomalies.

---

## Order state transitions
```text
                  +----------------------------------------+
                  |                 PLACED                 |
                  +----------------------------------------+
                     /                 |                  \
     restaurant_    /      restaurant_ |                   \ cancel_requested
     accepted      /       rejected    |                    \
                  v                    v                     v
          +--------------+      +--------------+      +--------------+
          |   ACCEPTED   |      |   REJECTED   |      |  CANCELLED   |
          +--------------+      +--------------+      +--------------+
           /            \        (Terminal)            (Terminal)
 dispatch_/              \ cancel_
 started /                \ requested
        v                  v
+------------------+  +--------------+
| OUT_FOR_DELIVERY |  |  CANCELLED   |
+------------------+  +--------------+
        |              (Terminal)
 order_ |
 deliv. |
        v
+------------------+
|    DELIVERED     |
+------------------+
    (Terminal)
```
- Orders in `OUT_FOR_DELIVERY` or `DELIVERED` disallow subsequent cancellation attempts (`cancel_requested` is ignored).
- All terminal states (`REJECTED`, `CANCELLED`, `DELIVERED`) ignore subsequent restaurant acceptance.

---

## Payment and refund state flow
```text
           +-----------------+
           |     UNPAID      |
           +-----------------+
                    |
                    | payment_confirmed
                    v
           +-----------------+
           |      PAID       |
           +-----------------+
                    |
                    | Order reaches REJECTED or CANCELLED:
                    | sets refund_due_paise = total_paise
                    v
           +-----------------------------------------------+
           | refund_processed (amount <= outstanding due)  |
           +-----------------------------------------------+
              /                                         \
             / partial refund                            \ full refund reached
            v  (refunded < due)                           v (refunded >= due)
   +-----------------+                           +-----------------+
   |      PAID       |                           |    REFUNDED     |
   | (accumulating)  |                           +-----------------+
   +-----------------+                               (Terminal)
```
- Asynchronous clearing: If an order was rejected or cancelled while `UNPAID`, a delayed `payment_confirmed` webhook transitions the payment to `PAID` and sets `refund_due_paise = total_paise`.
- Strict validation: Refunds require integer paise $> 0$, non-boolean types, paid status, and cannot exceed `refund_due_paise - refunded_paise`.

---

## Duplicate event strategy
- Every event is identified by an optional unique string `event_id`.
- Successful event processing appends `event_id` to `order["processed_event_ids"]`.
- When an event is delivered, `apply_order_event` checks:
  ```python
  if event_id is not None and event_id in out["processed_event_ids"]:
      return out
  ```
- Replays exit immediately without modifying status, amounts, or event history.

---

## Three edge cases I tested
1. **Python Boolean Type Intrusion:** Verified `amount_paise=True` and `amount_paise=False` are rejected and do not mutate refund totals.
2. **Post-Dispatch Cancellation Denial:** Verified customer cancellation received during `OUT_FOR_DELIVERY` preserves transit status without setting refund liability.
3. **Simultaneous Amount and Status Discrepancies:** Verified reconciliation accurately places orders diverging on both dimensions into both `amount_mismatches` and `status_mismatches`.
