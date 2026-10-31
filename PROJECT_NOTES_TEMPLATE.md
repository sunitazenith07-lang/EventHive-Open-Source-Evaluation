# Project notes

## Requirements completed
- **Order Lifecycle & State Transitions**: Enforced state transition boundaries (`PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`, `REJECTED`, `CANCELLED`). Invalid, out-of-order, or post-dispatch cancellation attempts leave status unmutated.
- **Event Idempotency**: Implemented early deduplication guards using `processed_event_ids` to ensure replaying events does not re-trigger side effects or duplicate event tracking.
- **Strict Refund Validation & Processing**:
  - Enforced eligibility checks (order must be `REJECTED` or `CANCELLED` with `payment_status == "PAID"`).
  - Used strict type checking (`type(amount) is int`) to reject booleans (`True`/`False`), floats, and strings.
  - Restricted refund amounts to positive integer paise strictly $\le$ outstanding balance (`refund_due_paise - refunded_paise`).
  - Automatically updated `payment_status` to `"REFUNDED"` when cumulative refunds reach `refund_due_paise`.
- **Order Reconciliation Engine**:
  - Evaluated amount and status discrepancies independently to correctly report orders experiencing simultaneous amount and status mismatches.
  - Normalized schema field differences between internal records (`total_paise`) and provider reports (`amount_paise`).
  - Guaranteed deterministic report output by sorting composite key sets.
- **Late Payment Handling**: Configured `payment_confirmed` events arriving on already cancelled or rejected orders to set `payment_status = "PAID"` and populate `refund_due_paise`.
- **State Distribution Summarization**: Implemented `summarise_orders_by_state` stretch function to aggregate order counts grouped by status.

## Files changed and why
- **`models.py`**: Updated `new_order` helper to construct canonical dictionary structures with default fields (`UNPAID` payment status, 0 refund balances, empty `processed_event_ids` list).
- **`service.py`**:
  - Implemented `_get_order_amount` helper to resolve `total_paise` vs `amount_paise` key asymmetry.
  - Refactored `apply_order_event` to enforce state transitions, idempotency guards, and strict refund bounds without mutating input dictionaries (`deepcopy`).
  - Refactored `reconcile_orders` to evaluate amount and status mismatches independently rather than using mutually exclusive `if / elif` branching.
  - Added `summarise_orders_by_state` function.
- **`tests/test_regression.py`**: Added 13 comprehensive regression tests covering boolean refund rejection, dual reconciliation mismatches, late payments, malformed payloads, non-string event IDs, and dictionary immutability.
- **Documentation**: Completed `approach.md`, `challenges.md`, `optimizations.md`, `ARCHITECTURE.md`, `ORDER_FLOW_NOTES.md`, and `TESTING.md`.

## Tests run
- **Command executed**: `python -m pytest -q`
- **Results**: `225 passed in 0.72s` (100% pass rate across `test_contract.py`, `test_acceptance_matrix.py`, and `test_regression.py`). Baseline improved from initial 62 failures down to 0 failures.

## Assumptions
- Order lifecycle progression follows strict unidirectional flow; orders cannot revert to prior states.
- Cancellation requests made after an order is dispatched (`OUT_FOR_DELIVERY` or `DELIVERED`) are ignored.
- Monetary amounts are non-negative fixed-precision integers representing paise.
- Order payloads are plain Python dictionaries to preserve JSON serialization compatibility.

## Known limitations
- **In-Memory Event Deduplication**: `processed_event_ids` operates as an in-memory `list` scan ($O(K)$ per order event). In distributed high-throughput production architectures, deduplication should be offloaded to database unique constraints on `(order_id, event_id)` or Redis TTL sets.
- **Single Currency Assumption**: All order values are assumed to be in integer paise. Multi-currency support or sub-unit conversion would require fixed-point math or `decimal.Decimal`.