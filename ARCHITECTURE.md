# OrderOps Architecture Notes

## Source File Map
- `service.py`: Core domain logic containing `apply_order_event()`, `reconcile_orders()`, and `export_awaiting_refund_csv()`.
- `models.py`: Helper `new_order()` defining canonical order dictionary schema.
- `fixtures.py`: Sample data fixtures for local execution.
- `main.py`: Entry point running offline reconciliation demo.
- `data/records.json`: Expanded synthetic benchmark dataset containing 150 internal orders, 163 provider records, 219 event examples, and an edge-case catalog.
- `tests/test_contract.py`: Contract tests verifying basic state flow, refund eligibility, and reconciliation.
- `tests/test_acceptance_matrix.py`: Parametrized test matrices for state transitions, event replays, refund bounds, and reconciliation.
- `tests/test_regression.py`: Regression test suite covering edge cases and full dataset validation.

## Order State Transitions
```
                 +-------------------+
                 |      PLACED       |
                 +---------+---------+
                           |
             +-------------+-------------+
             |                           |
             v                           v
      +--------------+            +--------------+
      |   ACCEPTED   |            |   REJECTED   | (Terminal)
      +------+-------+            +--------------+
             |
             +-------------+
             |             |
             v             v
+------------------+ +-----------+
| OUT_FOR_DELIVERY | | CANCELLED | (Terminal)
+--------+---------+ +-----------+
         |
         v
  +--------------+
  |  DELIVERED   | (Terminal)
  +--------------+
```
- An order in `PLACED` can transition to `ACCEPTED`, `REJECTED`, or `CANCELLED`.
- An order in `ACCEPTED` can transition to `OUT_FOR_DELIVERY` or `CANCELLED`.
- An order in `OUT_FOR_DELIVERY` can only transition to `DELIVERED`.
- Terminal states: `REJECTED`, `CANCELLED`, `DELIVERED`.

## Payment and Refund State Flow
```
[UNPAID] ---> (payment_confirmed) ---> [PAID]
                                         |
                       (order CANCELLED / REJECTED)
                                         |
                                         v
                         refund_due_paise = total_paise
                                         |
                                (refund_processed)
                                         |
                      +------------------+------------------+
                      |                                     |
                      v                                     v
       refunded_paise < refund_due_paise     refunded_paise == refund_due_paise
               [Remains PAID]                            [REFUNDED]
```

## Duplicate Event Strategy
- Every order tracks `processed_event_ids: list[str]`.
- Upon event receipt, if `event.get("event_id")` is already in `processed_event_ids`, `apply_order_event()` returns an unmutated copy immediately.
- Replaying events does not mutate state or add duplicate IDs.

## Edge Cases Tested
1. Cancellation request after order dispatch is blocked.
2. Event replay with conflicting payload is ignored.
3. Late payment confirmation after order cancellation/rejection properly sets refund due.
4. Over-refunding amounts exceeding outstanding due balance are rejected.
5. Dual mismatches in both amount and status are categorized simultaneously in reconciliation.
