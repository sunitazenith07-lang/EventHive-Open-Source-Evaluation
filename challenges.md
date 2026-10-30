# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The most deceptive challenge was Python's type hierarchy behavior around integer verification for financial amounts, combined with cumulative refund boundary handling. Specifically:
1. In Python, `isinstance(True, int)` evaluates to `True` because `bool` is a subclass of `int`. As a result, standard type checking like `isinstance(amount, int)` permitted boolean values (such as `True` or `False`) to be treated as valid numeric paise amounts.
2. Handling over-limit refunds: when a sequence of partial refunds arrives, if an incoming refund would cause the cumulative refunded amount to exceed `refund_due_paise`, what should happen? The service must not partially clamp the refund, nor must it throw an exception, but rather reject the excessive transaction while preserving the already refunded balance.

## 2. Evidence
Running the untouched baseline tests revealed numerous failures in `tests/test_acceptance_matrix.py`:
- `test_invalid_refund_amounts_are_ignored[True]`:
  ```
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]
  AssertionError: assert 1 == 0  # True was evaluated as 1 paisa!
  ```
- `test_invalid_refund_amounts_are_ignored[-10]`:
  ```
  FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[-10]
  AssertionError: assert -10 == 0
  ```
- `test_refunds_cannot_exceed_due[4000-2000]`:
  ```
  FAILED tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due[4000-2000]
  AssertionError: assert 6000 == 4000
  ```
- `test_payment_event_replay_idempotent[EV-000]`:
  ```
  AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']
  ```

## 3. What I tried
- *Trial 1 (Basic type check):* Tested `isinstance(amount, int) and amount > 0`. While this eliminated floats (`0.5`) and negative values (`-10`), the test `test_invalid_refund_amounts_are_ignored[True]` still failed because in Python `isinstance(True, int)` is `True` and `True > 0` is `True`.
- *Trial 2 (Clamping refund amount):* Considered clamping `amount = min(amount, outstanding)`. However, the acceptance contract and `test_refunds_cannot_exceed_due` required that an over-limit refund request be ignored in its entirety (`expected = first + second if first + second <= 5000 else first`), rather than partially applied.
- *Trial 3 (Idempotency deduplication):* Initially considered deduplicating `processed_event_ids` at the end using `list(set(...))`. However, that mutated the order of processed events, did not prevent re-executing event state mutations (e.g., repeatedly applying status changes or re-triggering refunds), and failed to satisfy the contract requirement that replay must not re-process logic.

## 4. Resolution
1. **Strict Type and Value Guard:** Replaced naïve checks with:
   ```python
   is_valid_int = isinstance(amount, int) and not isinstance(amount, bool) and amount > 0
   ```
   This strictly enforces positive integer paise and screens out boolean values, floats, strings, and collections.
2. **Strict Outstanding Amount Bound:** Checked remaining refundable balance before applying any refund:
   ```python
   outstanding = due - already_refunded
   if amount <= outstanding:
       out["refunded_paise"] = already_refunded + amount
       if out["refunded_paise"] >= due:
           out["payment_status"] = "REFUNDED"
   ```
   If `amount > outstanding`, the event is safely ignored without altering `refunded_paise`.
3. **Early Idempotency Gate:** Placed an early guard at the top of `apply_order_event`:
   ```python
   event_id = event.get("event_id")
   if event_id is not None and event_id in out["processed_event_ids"]:
       return out
   ```
   This guarantees that duplicate events return the order immediately without side effects.

## 5. Proof and regression prevention
- **Demonstration:** All 20 parameterized instances of `test_payment_event_replay_idempotent`, all 15 instances of `test_invalid_refund_amounts_are_ignored`, and all 20 instances of `test_refunds_cannot_exceed_due` passed immediately.
- **Dedicated Regression Tests Added:**
  - `test_replay_with_conflicting_payload_is_ignored`: Verifies that if an attacker or buggy upstream service resends a known `event_id` with a different payload or amount, the conflicting payload is completely ignored.
  - `test_partial_refund_then_full_refund_sequence`: Verifies exact two-step refund accumulation (`1000 + 2000 = 3000`) transitioning `payment_status` to `"REFUNDED"`.
  - `test_boundary_amounts_one_paisa`: Verifies exact 1 paisa edge case lifecycle.

## 6. Unresolved challenge or next step
- In this offline in-memory implementation, `processed_event_ids` is stored as an in-memory list within each order record. In a high-throughput distributed system with millions of orders and long event histories, storing event IDs directly on the order document could lead to unbounded document growth.
- Next step for a production system: Store processed event IDs in an indexed idempotency ledger (e.g. Redis key with TTL or dedicated idempotency table in PostgreSQL) to support high-scale event streaming with sub-millisecond deduplication checks.
