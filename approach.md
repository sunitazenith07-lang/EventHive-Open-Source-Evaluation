# approach.md - Required submission

## 1. Baseline

- I checked the initial runtime with `python --version`: Python 3.14.5.
- The first `python -m pytest -q` attempt could not start because pytest was missing. I installed the repository's declared development dependency with `python -m pip install -r requirements-dev.txt`.
- Before changing the service, the test suite reported **62 failed, 150 passed, 1 warning in 1.08s**.
- Before the fix, `python -m main` reported no status mismatches even though fixture ORD-102 had different internal/provider statuses.

## 2. Codebase understanding

- `models.py:new_order` builds the in-memory order dictionary. `service.py:apply_order_event` returns an updated copy; `service.py:reconcile_orders` compares internal/provider records by `order_id`.
- `fixtures.py` supplies the small synthetic demo inputs, and `main.py` runs reconciliation and prints its categories.
- I inspected both visible test modules: `tests/test_contract.py` and `tests/test_acceptance_matrix.py`. They cover transition validity, input immutability, replay, refund eligibility and bounds, mismatch reporting, unknown events, and deterministic results.
- The service is a synchronous, offline example using Python dictionaries and lists; it does not persist state or call a payment provider. The problem statement and `data/README.txt` identify the records as synthetic.

## 3. Investigation and implementation strategy

- **Replay idempotency:** The starter appended every `event_id` without checking whether it had already been processed. The replay tests failed because the second application duplicated the ID. I added guards for missing/invalid event identifiers and unsupported event types, and return the copied order without reapplying an already-recorded event. I also added a regression test that replays a partial refund and verifies the refunded amount stays unchanged.
- **Refund validation:** The starter added any `amount_paise` directly, including amounts for ineligible orders and invalid values. I made refund application conditional on a cancelled/rejected paid order, a positive integer amount (excluding booleans), valid positive due and refunded integers, and an amount no greater than the outstanding due. Payment status changes to `REFUNDED` only when accumulated refunds equal the due amount.
- **Reconciliation status:** The starter compared amounts but placed equal-amount records in `matched` without comparing statuses. I added a separate status comparison and only classify a record as matched when both amount and status agree. Rows without an `order_id` are skipped because they cannot be reliably keyed.
- The changes keep the existing in-memory API and state representation; they do not add dependencies or alter CI.

## 4. Implementation decisions

- I kept the original recognized state transitions and deep-copy behavior, which preserve the tested transition rules and input immutability.
- Refund validation occurs before changing either refund total or payment status so invalid notifications cannot partially mutate the result.
- I kept deterministic sorted order IDs in reconciliation. Amount and status mismatches are separate report categories and can both be reported for one order.
- Assumptions: event IDs are non-empty strings; the supported event names are the seven in the problem statement; refunds use integer paise. Invalid or unsupported event payloads are ignored without changing order state.

## 5. Verification

- I added regression tests in `tests/test_contract.py` for refund replay and missing/malformed event fields. I did not remove, skip, weaken, or edit existing tests.
- `python -m pytest -q` — after the service cleanup and five additional edge-case tests, **219 passed in 0.58s** on Python 3.14.5 with no warnings.
- `requirements-dev.txt` now limits pytest to versions below 9; the warning seen in the initial post-fix run no longer appears with the installed pytest 8.4.2.
- `python -m main` completed and reported `status_mismatches: ['ORD-102']`, along with the expected fixture missing-side and amount-mismatch categories.
- I ran a payment → acceptance → cancellation → full refund sequence. The observed states were `PLACED/PAID`, `ACCEPTED/PAID`, `CANCELLED/PAID` with 1000 paise due and zero refunded, then `CANCELLED/REFUNDED` with 1000 paise refunded.
- The local interpreter is Python 3.14.5; CI specifies Python 3.11. I did not run the suite under Python 3.11.
