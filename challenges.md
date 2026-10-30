# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
The most important edge case was a payment confirmation arriving after an order had already been cancelled. In the starter logic, refund due was set only when the order was cancelled while payment was already marked paid.

## 2. Evidence
The baseline test run reported **62 failed, 150 passed**. The starter demo also failed to report the `ORD-102` status difference.

## 3. What I tried
- Ran the baseline test suite and offline demo before editing.
- Read the state transition and refund logic in `service.py` alongside the acceptance tests.
- Added a focused test for payment confirmation after cancellation and re-ran the full suite.

## 4. Resolution
When payment is confirmed for an already cancelled or rejected order, the handler now sets `refund_due_paise` to the positive integer order total. Refund processing separately verifies eligibility and checks the requested amount against the outstanding balance.

## 5. Proof and regression prevention
- `test_payment_confirmed_after_cancellation_sets_refund_due` covers the late-payment case.
- `test_duplicate_refund_event_is_idempotent` ensures replaying a partial refund cannot increase the refund twice.
- `test_reconciliation_reports_amount_and_status_mismatches_separately` verifies both mismatch categories can be reported for one order.
- Final `python -m pytest -q`: **216 passed**.

## 6. Unresolved challenge or next step
Duplicate summary rows for one order ID still use the last row in each input list. A future change could define an explicit duplicate-record policy and report duplicates instead of silently choosing one.
