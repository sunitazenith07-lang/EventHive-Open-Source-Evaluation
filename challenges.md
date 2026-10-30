# challenges.md

## 1. Challenge or confusing behaviour
The hardest edge case was not a lifecycle rule; it was malformed input. The service was assuming every event and every reconciliation row was a dictionary. In practice, the contract explicitly says invalid events, missing fields, and duplicates should not corrupt state, but the code dereferenced `.get()` on `None`, strings, and lists before validating the shape.

## 2. Evidence
The reproducer was a small Python snippet and the new regression tests. The actual failure message was:

- `AttributeError: 'NoneType' object has no attribute 'get'`
- `AttributeError: 'str' object has no attribute 'get'`
- `AttributeError: 'list' object has no attribute 'get'`

The failing cases were exactly the malformed inputs the contract says should be no-ops.

## 3. What I tried
I reproduced the issue with minimal examples in the test suite and by running `pytest -q` after adding the regression coverage. After each attempt, I checked the call stack in `service.py` to confirm the root cause was the unconditional `.get()` access before defensive validation.

## 4. Resolution
The root cause was missing input validation in both `apply_order_event()` and `reconcile_orders()`. I fixed the code by returning the original order for non-dict event payloads and skipping non-dict or missing-ID rows during reconciliation. This addressed the cause instead of hiding the symptom because the state machine now rejects malformed inputs before any mutation occurs.

## 5. Proof and regression prevention
The regression tests in `tests/test_contract.py` and `tests/test_acceptance_matrix.py` now cover:
- `None` event payloads
- empty and unknown event dic
- non-dict event values
- `None` reconciliation rows
- provider-only and internal-only records with malformed input

## 6. Unresolved challenge or next step
No unresolved failures remain in the repository test suite. If more edge cases appear later, the next step would be to validate the event schema and order_id values at the service boundary before state updates, but the current fix already matches the contract’s no-crash/no-mutation requirement.
