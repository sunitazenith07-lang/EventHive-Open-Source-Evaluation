# approach.md

## 1. Baseline
- Commands run before editing: `pytest -q` for the focused contract and acceptance suite, followed by the full `pytest -q` verification run.
- Initial test result: the repository initially reported 213 passing tests in the focused suite, but the malformed-input regressions exposed latent crashes in the order-state engine.
- Demo/output observed: failures reproduced as `AttributeError` calls caused by `.get()` being invoked on `None`, strings, and list payloads.

## 2. Codebase understanding
- Files inspected: `service.py`, `models.py`, `tests/test_contract.py`, `tests/test_acceptance_matrix.py`, and the project contract notes.
- The relevant flow is: `new_order()` creates a default order, then `apply_order_event()` mutates a copy of the order, and `reconcile_orders()` compares internal/provider summaries.
- I confirmed the root cause by reproducing malformed inputs like `None`, `{}`, `"bad"`, and `["bad"]` and by checking the call stack in `service.py`.

## 3. Investigation and implementation strategy
- Issue 1: `apply_order_event()` assumed every event was a dict and crashed on `None` or non-dict input.
- Hypothesis: guard against malformed event payloads before reading keys and return the original order unchanged.
- Evidence: failing regression tests for `None`, `{}`, and list payloads reproduced the crash.
- Fix: short-circuit if `event` is not a dict, and skip processing when the event type is missing or invalid.
- Issue 2: `reconcile_orders()` assumed every row was a dict and crashed on `None` entries.
- Hypothesis: ignore non-dict rows and missing `order_id`s instead of indexing into them.
- Evidence: the regression tests for `[None]` and provider-only rows failed with `AttributeError: 'NoneType' object has no attribute 'get'`.
- Fix: build the internal/provider maps only from valid dict rows with a non-`None` `order_id`.

## 4. Implementation decisions
- I kept the fix minimal and behaviorally safe: malformed or unknown events are now no-ops, and malformed reconciliation rows are ignored rather than causing a crash.
- I did not add hidden special cases or alter the intended lifecycle rules; I only added input validation around the existing state machine.
- The alternative of coercing invalid payloads to defaults was rejected because the contract requires invalid inputs to avoid mutating state and to fail safely.

## 5. Verification
- Tests added or changed: regression tests for malformed event payloads and malformed reconciliation rows in `tests/test_contract.py` and `tests/test_acceptance_matrix.py`.
- Commands run and actual results: `pytest -q` -> `233 passed in 0.06s`.
- Edge cases verified: `None` event payloads, empty dicts, unknown event types, non-dict events, `None` reconciliation rows, and provider-only records.
- Remaining failures or known limitations: none in the repository test suite after the fix.
