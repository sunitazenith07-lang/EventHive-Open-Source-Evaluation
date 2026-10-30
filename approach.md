# approach.md - Required submission

## 1. Baseline
- Commands run before editing:
  - `python -m pytest -q`
  - `python -m main`
- Initial test result: 212 tests collected, 150 passed, 62 failed.
- Demo/output observed: reconciliation reported `ORD-101` and `ORD-102` as amount mismatches and no status mismatches because internal `total_paise` was compared only against provider `amount_paise`, and status differences were ignored.

## 2. Codebase understanding
- Important files and functions inspected: `service.py` (`apply_order_event`, `reconcile_orders`), `models.py` (`new_order`), `fixtures.py`, `main.py`, tests under `tests/`, `data/records.json`, README and problem statement.
- Order lifecycle traced: `PLACED` -> `ACCEPTED` -> `OUT_FOR_DELIVERY` -> `DELIVERED`; rejection/cancellation can occur before dispatch; cancellation after dispatch is ignored.
- Payment and refund flow traced: payment confirmation sets `PAID`; rejection/cancellation while paid sets `refund_due_paise` to the order total; refund events accumulate `refunded_paise` and set `REFUNDED` only at full due.
- How I confirmed understanding: ran the baseline suite, inspected every acceptance-matrix case, and traced `data/records.json` event examples.

## 3. Investigation and implementation strategy
- Issue 1, idempotency: symptom was duplicate refunds on replayed events. Hypothesis: `event_id` was never checked. Evidence: `test_duplicate_event_is_idempotent` and payment replay tests. Fix: return early when an identified `event_id` is already in `processed_event_ids`.
- Issue 2, refund safety: symptom was invalid, ineligible, or over-limit refunds being applied. Hypothesis: `refund_processed` had no eligibility, type, sign, or cap checks. Evidence: refund contract and acceptance-matrix tests. Fix: validate status, payment status, integer paise amount, positivity, and outstanding due before mutating.
- Issue 3, reconciliation: symptom was status mismatches reported as matches and false amount mismatches in the demo. Hypothesis: only `amount_paise` was compared and status was ignored. Evidence: reconciliation contract/matrix tests and demo output. Fix: compare internal `total_paise` as a fallback amount, compare status independently, and report both categories.

## 4. Implementation decisions
- Main changes and why: added an idempotency guard, strict refund validation, payment-after-rejection handling, deterministic reconciliation with independent mismatch categories, and defensive input handling.
- Alternatives considered and why rejected: recording every event ID even when invalid was chosen over skipping IDs because it preserves replay-safe idempotency; first-occurrence handling for duplicate order IDs was chosen because the report schema has no duplicate-specific category.
- Assumptions: internal monetary amount may be stored as `total_paise` or `amount_paise`; events without `event_id` cannot be deduplicated; duplicate order IDs collapse to their first occurrence.

## 5. Verification
- Tests added or changed: added `tests/test_regressions.py` with 14 regression tests; no existing tests changed.
- Commands run and actual results: `python -m pytest -q` -> 226 passed, 0 failed; `python -m main` -> matched `ORD-101`, missing provider `ORD-103`, missing internal `ORD-104`, no amount mismatches, status mismatch `ORD-102`.
- Edge cases verified: duplicate refund replay, invalid refund types, over-limit refunds, cancellation after dispatch, payment after rejection, combined reconciliation mismatches, empty/malformed reconciliation input.
- Remaining failures or known limitations: documentation still to be completed; duplicate order IDs are not explicitly reported; anonymous events are not deduplicated.
