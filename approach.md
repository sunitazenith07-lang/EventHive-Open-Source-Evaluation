# Approach and Implementation Notes

## 1. Understanding the problem

I started by going through the problem statement and understanding what the service was expected to handle.

The main areas were order state transitions, payment confirmation, cancellation, refunds and reconciliation between internal records and provider records.

One thing that became clear during the investigation was that order status and payment status needed to be handled separately. For example, an order can be cancelled while its payment is still pending, or it can be rejected while a partial refund is being processed.

## 2. Initial investigation

Before making changes, I checked the project structure and ran the existing test suite.

The initial test run showed:

- 150 tests passing.
- 62 tests failing.
- 212 tests collected.

I then inspected `service.py`, `models.py`, `fixtures.py` and the test files to understand how the application worked.

Most of the problems were concentrated in `apply_order_event()` and `reconcile_orders()`.

## 3. Changes made to event processing

The first area I worked on was event handling.

I added validation for event IDs and a duplicate-event check. This prevents the same event from being applied repeatedly when its identifier has already been recorded.

I also reviewed the supported event types and added checks so that unknown or malformed event inputs do not accidentally change order state.

Another scenario I investigated was a payment confirmation arriving after an order had already been cancelled or rejected. In that situation, the order should retain its existing status, but the system still needs to establish the appropriate refund obligation.

## 4. Changes made to refund processing

Refund processing needed several checks before the refunded amount could be updated.

I added validation to ensure that:

- The order is cancelled or rejected.
- The payment has been confirmed.
- The refund obligation is positive.
- The refund amount is a positive integer.
- Boolean values are not accepted as integer amounts.
- The refund does not exceed the remaining amount due.

The calculation uses the outstanding amount:

Outstanding refund = Refund due - Already refunded

I also made sure that a partial refund leaves the payment status as PAID. The status changes to REFUNDED only after the complete refund obligation has been fulfilled.

## 5. Changes made to reconciliation

The original reconciliation logic had two main problems.

First, it compared amount fields using the same dictionary key, even though internal and provider records used different field names.

The internal records used `total_paise`, while provider records used `amount_paise`.

I added amount normalization before comparing the records.

Second, the original implementation did not properly compare order statuses. I changed the comparison so that amount differences and status differences are reported independently.

I also added validation for duplicate order IDs, missing identifiers and malformed reconciliation records.

The report continues to use the five categories defined by the starter:

- matched
- missing_from_provider
- missing_from_internal
- amount_mismatches
- status_mismatches

## 6. Testing approach

I used the existing contract tests and acceptance matrix to check the changes.

Rather than relying on the full test suite after every change, I also ran individual tests for specific problems.

Some additional regression cases were added for scenarios that were not adequately covered by the original tests, including late payment confirmation, duplicate order IDs and malformed inputs.

After making changes, I reran the complete test suite to check that existing behaviour was preserved.

## 7. Implementation decisions

A few decisions influenced the implementation:

- The original order dictionary should not be modified, so event processing works on a copied record.
- Refund amounts are handled as integer paise.
- An excessive refund is rejected rather than partially applied or silently capped.
- Reconciliation output should be deterministic.
- Duplicate order IDs should be rejected instead of silently overwriting earlier records.
- Missing or malformed comparison values should not be treated as successful matches.

## 8. Final verification

The final local test run collected 254 tests, and all 254 passed.

The application demonstration also produced the expected reconciliation output for the supplied sample records.

The changes were concentrated mainly in `service.py`, with additional regression tests and project documentation.

## 9. Scope and limitations

This implementation is intended for the supplied offline evaluation.

It does not include a production database, live payment provider integration or actual webhook processing.

The focus was on preserving valid order and payment states, preventing incorrect refunds and producing reliable reconciliation results.