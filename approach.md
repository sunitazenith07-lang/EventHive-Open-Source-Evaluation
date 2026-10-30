# approach.md - Required submission

## 1. Baseline
- **Commands run:** `python --version`, `pip install -r requirements-dev.txt`, `python -m pytest -q`, `python -m main`
- **Initial test result:** `62 failed, 150 passed`
- **Demo output (`python -m main`):**
  ```
  matched: []
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  `ORD-101` was a false mismatch; `ORD-102` status difference was completely missed.

## 2. Codebase understanding
- `models.py` — creates order dicts with keys: `order_id`, `total_paise`, `status`, `payment_status`, `refund_due_paise`, `refunded_paise`, `processed_event_ids`.
- `service.py` — two functions: `apply_order_event` (state machine) and `reconcile_orders` (two-way ledger diff).
- Grouped the 62 failures into 3 categories by reading the failing test names, which pointed directly to 3 root causes in `service.py`.

## 3. Investigation and fixes

**Issue 1 — No idempotency**
- Replaying an event always appended the event_id again and re-applied changes.
- Fix: added early return if `event_id in out["processed_event_ids"]` before any logic runs.

**Issue 2 — Unsafe refund logic**
- Refunds were applied to any order with any amount value (including `True`, `-1`, `"10"`, floats).
- Fix: three layered checks — `type(amount) is int and amount > 0` (note: `isinstance` would pass booleans since `bool` subclasses `int`), eligibility (`status` in `REJECTED`/`CANCELLED`, `payment_status == "PAID"`), and overflow guard (`amount <= refund_due_paise - refunded_paise`).

**Issue 3 — Reconciliation missing status check and key mismatch**
- Status was never compared; matching only checked `amount_paise` which is `None` on internal records (they use `total_paise`).
- Fix: read `amount_paise` if present else fall back to `total_paise`; check amount and status independently so an order with both mismatches appears in both lists.

## 4. Implementation decisions
- `deepcopy` preserves input immutability (nested `processed_event_ids` list would be shared with a shallow copy).
- Invalid events and duplicates silently no-op rather than raise, per spec: *"handle duplicates without corrupting state"*.
- Late `payment_confirmed` on already `REJECTED`/`CANCELLED` orders now sets `refund_due_paise`, handling out-of-order payment arrivals.

## 5. Verification
- Added `tests/test_regression.py` with 12 targeted regression tests covering all three fixes.
- Final result: `224 passed, 0 failed`.
- Demo output after fix:
  ```
  matched: ['ORD-101']
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: []
  status_mismatches: ['ORD-102']
  ```
