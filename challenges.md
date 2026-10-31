# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour

The main challenge was locating three independent defects in one small service: replay handling, refund validation, and status reconciliation. A green subset of tests would not have shown that the demo's `matched`/mismatch classification was incomplete, so I ran the full acceptance suite and traced each failing assertion to its corresponding branch in `service.py`.

## 2. Evidence

- Baseline: `python -m pytest -q` initially reported **62 failed, 150 passed, 1 warning** after installing pytest.
- Replay tests showed the same event ID being appended twice; both the contract replay test and the parametrized acceptance replay cases failed.
- Refund tests exposed ineligible and invalid refunds being added, and accepted refund totals exceeding `refund_due_paise`.
- The status mismatch test failed because equal amounts were enough for the starter to put an order in `matched`. The demo's initial `status_mismatches: []` was also inconsistent with ORD-102's differing fixture statuses.
- During implementation, I ran the sequence `payment_confirmed`, `restaurant_accepted`, `cancel_requested`, `refund_processed` for a 1000-paise order. The output showed the expected transitions and final `REFUNDED` payment state.

## 3. What I tried

1. Checked the Python version and ran the test suite before edits.
2. Installed the declared pytest dependency after the first test command reported `No module named pytest`.
3. Read the relevant service branches alongside the failed contract and acceptance assertions.
4. Changed the producer of each incorrect result rather than altering tests: deduplicate before applying event effects, validate refund eligibility and bounds before updating totals, and compare reconciliation statuses explicitly.
5. Added regression tests for replaying a partial refund and ignoring missing/malformed event fields, then reran the full suite and the demo.

## 4. Resolution

Replay protection now returns the copied order when an event ID has already been processed. Refund handling accepts only a positive integer amount within the remaining due for an eligible paid cancelled/rejected order; it marks the payment refunded only on exact completion. Reconciliation reports amount and status differences separately and calls a record matched only when both values agree. The full test run after these changes passed **214 tests**.

## 5. Proof and regression prevention

- Existing replay, refund-eligibility, invalid-amount, cumulative-bound, and reconciliation mismatch matrices now pass.
- New `test_duplicate_refund_event_is_idempotent` verifies repeated delivery of the same refund event does not increase `refunded_paise` twice.
- New `test_missing_or_malformed_event_fields_do_not_change_order` verifies absent event fields and an unhashable invalid type do not change the order.
- Full result after adding eight additional edge-case tests and cleaning up `service.py`: `python -m pytest -q` — **222 passed in 1.19s**, with no warnings.
- Demo verification: `python -m main` reports ORD-102 in `status_mismatches`.

## 6. Unresolved challenge or next step

The validation was run on Python 3.14.5, while `.github/workflows/tests.yml` configures Python 3.11; cross-version execution remains unverified locally. The service remains an in-memory simulation without durable state or a real provider integration, consistent with the project scope.

The organizer was reported in this chat to allow AI use, but checked-in `CONTRIBUTING.md` and `STUDENT_PROBLEM_STATEMENT.md` still prohibit it. Confirm the authoritative event policy and reconcile the repository guidance before submitting.
