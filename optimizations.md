# optimizations.md

## 1. Baseline and objective
The main problem was not throughput but correctness and defensive programming. The service was blindly dereferencing malformed event and reconciliation inputs instead of short-circuiting them, which created crash paths even though the contract expects invalid inputs to be ignored safely.

## 2. Options considered
1. Coerce malformed payloads into defaults.
   - Benefit: could stop immediate crashes.
   - Risk: hidden data loss and silent mutation of order state.
   - Rejected because it would mask invalid inputs and violate the no-mutation contract.
2. Add explicit validation guards before property access.
   - Benefit: preserves the existing state machine and stops invalid input early.
   - Risk: slightly more branching logic.
   - Chosen because it matches the specification and keeps the behavior explicit.
3. Pre-normalize every row before comparison.
   - Benefit: more centralized validation.
   - Risk: added complexity without clear user-facing gain.
   - Rejected as unnecessary for the current scope.

## 3. Changes implemented
- Change: added early checks in `apply_order_event()` for `event` being a dict and in `reconcile_orders()` for `row` being a dict with a valid `order_id`.
- Reason: this prevents invalid data from reaching `.get()` and preserves state without changing valid transitions.
- Tests used to protect correctness: the new regression cases in `tests/test_contract.py` and `tests/test_acceptance_matrix.py`.
- Measurement: no benchmark was necessary because the improvement is correctness-oriented; the verifying run was `pytest -q`, which passed with `233 passed in 0.06s`.

## 4. Trade-offs
This change adds a little logic branching, but the trade-off is worthwhile because it keeps behavior deterministic and safe when the dataset includes malformed rows or unexpected event payloads. The complexity increase is minimal and the code remains easy to reason about.

## 5. Further improvements
With more time, I would add a small helper for payload validation so event and reconciliation checks share one contract and remain consistent across future order lifecycle changes. That would reduce duplication, but the current fix is already sufficient for correctness and maintainability.
