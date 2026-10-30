# approach.md - Required submission

## 1. Baseline
- Commands run before editing: `python -m pytest -q`; `python -m main`.
- Initial test result (include the actual summary): **62 failed, 150 passed**.
- Demo/output observed: The demo completed but did not report the status mismatch for `ORD-102`.

## 2. Codebase understanding
- Important files and functions inspected: `service.py` (`apply_order_event`, `reconcile_orders`), `models.py` (`new_order`), `fixtures.py`, `main.py`, and both test files.
- Order lifecycle or data flow traced: `new_order` creates an order; `apply_order_event` copies it and applies an event; reconciliation compares internal and provider rows by order ID; `main.py` prints the fixture reconciliation.
- How you confirmed your understanding: Read the acceptance tests and ran the demo and full test suite before editing.

## 3. Investigation and implementation strategy
- Issue 1: Duplicate events were processed because the handler did not check recorded IDs before applying event effects. I added event-ID validation and an early return for already processed IDs; refund replay and payment replay tests cover this.
- Issue 2: Refund values were added without checking type, eligibility, or outstanding balance. I added checks for a paid cancelled/rejected order, positive integer paise amounts (excluding booleans), and the remaining due balance. Refund matrix tests and new replay coverage verify the behavior.
- Issue 3 (if applicable): Reconciliation considered amount equality but not status. I compare both fields independently and only mark an order matched if both are present and equal. The mismatch matrix and demo output verify this.

## 4. Implementation decisions
- Main changes and why: Validate event inputs and replay IDs; constrain refunds to the valid outstanding balance; establish refund due if payment is confirmed after cancellation/rejection; compare reconciliation status as well as amount.
- Alternatives considered and why rejected: I did not add reconciliation result categories or dependencies because the existing report shape is sufficient for the required comparisons.
- Assumptions: Recognized events are recorded even when the current state does not allow their transition. Unknown or malformed events are ignored without being recorded. Duplicate order IDs in reconciliation input continue to resolve to the last row.

## 5. Verification
- Tests added or changed: Added tests for duplicate refund replay, malformed/missing event fields, late payment after cancellation, and simultaneous amount/status mismatches.
- Commands run and actual results: Baseline `python -m pytest -q` — **62 failed, 150 passed**. Final `python -m pytest -q` — **216 passed**. `python -m main` — completed and reported `ORD-102` in `status_mismatches`. `git diff --check` — passed.
- Edge cases verified: Refund replay; invalid event fields; payment confirmed after cancellation; cancellation after dispatch; excessive or ineligible refunds; amount and status mismatches.
- Remaining failures or known limitations: No test failures remain. Duplicate order IDs are not reported as anomalies; the last row wins. No performance benchmark was run.
