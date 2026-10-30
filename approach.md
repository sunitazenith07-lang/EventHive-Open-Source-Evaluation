# approach.md

Environment: macOS, VS Code terminal, Python 3.14.7 in a `.venv`, pytest from `requirements-dev.txt`.

## 1. Baseline
- Commands run before editing: `python -m pip install -r requirements-dev.txt`, `python -m pytest -q`, `python -m main`.
- Initial test result: **62 failed, 150 passed in 0.25s**.
- Demo output observed on the untouched starter:
  ```
  matched: []
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: ['ORD-101', 'ORD-102']
  status_mismatches: []
  ```
  Two things looked wrong. ORD-101 and ORD-102 are reported as amount mismatches although both sides hold the same number (45900 and 129900), and ORD-102 (internal ACCEPTED, provider CANCELLED) is not reported as a status mismatch.

## 2. Codebase understanding
- Files inspected: `service.py` (`apply_order_event`, `reconcile_orders`), `models.py` (`new_order`), `fixtures.py`, `main.py`, `tests/test_contract.py`, `tests/test_acceptance_matrix.py`, `data/README.txt`, the three templates, `STUDENT_PROBLEM_STATEMENT.md`.
- Lifecycle traced: `PLACED -> ACCEPTED -> OUT_FOR_DELIVERY -> DELIVERED`, with `PLACED -> REJECTED` and `PLACED/ACCEPTED -> CANCELLED`. Dispatch is only allowed from ACCEPTED, delivery only from OUT_FOR_DELIVERY, so a cancel after dispatch is ignored. Payment runs `UNPAID -> PAID -> REFUNDED`. When a paid order becomes REJECTED or CANCELLED, `refund_due_paise` is set to `total_paise`; `refunded_paise` then grows with each `refund_processed` event.
- How I confirmed it: I read the parametrisations of every failing test, grouped the 62 failures by test name, and checked that the groups add up to 62:

  | Group | Failing tests | Count |
  |---|---|---|
  | No duplicate check | `test_payment_event_replay_idempotent` (20), `test_duplicate_event_is_idempotent` (1) | 21 |
  | Refund branch trusts everything | `test_invalid_refund_amounts_are_ignored` (13), `test_refund_eligibility_matrix` (10), `test_refunds_cannot_exceed_due` (7), 3 contract tests | 33 |
  | Status never compared | `test_reconciliation_status_mismatch_matrix` (7), `test_reconcile_reports_status_difference` (1) | 8 |

## 3. Investigation and implementation strategy
- **Issue 1, idempotency.** Symptom: `processed_event_ids == ['e1', 'e1']` after replaying one event. Hypothesis: the list is only ever written (the `append` at the bottom runs for every event) and never read. Evidence: reading the function, and replaying the same `payment_confirmed` event twice in a Python shell. Fix: a guard placed before the `if/elif` chain that returns the unchanged copy when the id is unusable or already recorded.
- **Issue 2, refunds.** Symptoms: a 6000 refund applied against 4000 due, refunds on PLACED/UNPAID orders, `-10` accepted, `True` counted as 1 paise. Hypothesis: `refunded_paise += amount` runs with no validation, and `>=` marks REFUNDED even when nothing was due. Evidence: the 33 failing tests above, and `isinstance(True, int)` being `True` in Python. Fix: the refund is applied only if the amount is a positive int (not bool), the order is REJECTED/CANCELLED and PAID, and the amount is at most `refund_due_paise - refunded_paise`; REFUNDED is set only when refunded equals due.
- **Issue 3, reconciliation.** Symptom: `status_mismatches` always empty and the demo flagging equal amounts. Hypothesis: the status is never compared, and internal orders built by `new_order` carry `total_paise` while the reconciler reads `amount_paise`. Evidence: the starter demo output above. Fix: amount and status are two independent checks, `matched` requires both to agree, and the amount falls back to `total_paise` when `amount_paise` is absent.
- **Issue 4, found by review rather than by a failing test.** `payment_confirmed` set PAID unconditionally, so a late confirmation turned a fully REFUNDED order back to PAID. A payment arriving after a cancellation also left `refund_due_paise` at 0, so that money could never be refunded. Fix: payment only moves UNPAID to PAID, and a payment on an already REJECTED/CANCELLED order records the refund due.

## 4. Implementation decisions
- Main changes: all in `service.py`. Small helpers (`_is_valid_id`, `_is_valid_amount`, `_mark_refund_due`, `_apply_refund`, `_index_by_order_id`, `_amount`) so each rule has one place.
- Alternatives considered and rejected:
  - Record an event id only when it was applied. Better for late refund notifications, but a bigger restructure of the `if/elif` chain; I kept "record every event with a usable id" and documented the cost.
  - Trim an over-limit refund to the outstanding amount. Rejected: the tests expect an over-limit refund to be ignored entirely.
  - Table-driven transitions. Clearer on paper, but a larger diff than the bug needed.
  - Accept integral floats such as `1000.0`. Rejected: the brief says integer paise.
- Assumptions: events with a missing or unusable `event_id` are ignored; reconciliation rows without a usable `order_id` are skipped; for duplicate ids in one list the last record wins; an order that differs in both amount and status appears in both mismatch lists.

## 5. Verification
- Tests added: `tests/test_regressions.py` (34 cases, see `TESTING.md`). Run against the untouched starter `service.py`, 29 of those 34 cases fail; the other 5 are guards for behaviour that must keep working.
- Commands and results: `python -m pytest -q` after the fix and before the new tests gave **212 passed in 0.04s**; with the regression tests it gives **246 passed**. `python -m main` now prints `matched: ['ORD-101']` and `status_mismatches: ['ORD-102']`.
- Edge cases verified: replayed refund, missing and invalid event ids, bool/float/string refund amounts, refund after full refund, late payment after refund, payment after cancellation, mixed-type order ids, rows without order id, `None` inputs. Details in `TESTING.md` and `ORDER_FLOW_NOTES.md`.
- Remaining limitations: see `challenges.md` section 6. In short, a refund notification that arrives before the cancellation is ignored and its id is spent.

## 6. How I worked
I used an AI assistant (Claude) for explanations, for analysing the failing tests, and for drafting the final `service.py`, the regression tests and these notes. See `AI_USAGE_TEMPLATE.md` for the full declaration.