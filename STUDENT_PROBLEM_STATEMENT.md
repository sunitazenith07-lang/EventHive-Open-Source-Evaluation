# OrderOps: Order Failure, Cancellation & Refund Reconciliation

**Track:** Food-delivery operations | **Language:** Python 3.10+ | **Time:** 24-hour evaluation

## Scenario
A food-delivery platform can confirm payment before the restaurant accepts an order. The restaurant may reject it; customers may cancel before dispatch; and refund notifications can arrive late or more than once. The service must not duplicate a refund or confuse a partial refund with a completed refund.

This is a simulated, offline project inspired by common food-delivery workflows. It is not any company's internal code and does not use real customers or payment APIs.

## Required behaviour
1. Process the supplied events: payment_confirmed, restaurant_accepted, restaurant_rejected, cancel_requested, dispatch_started, order_delivered and refund_processed.
2. Enforce valid transitions. A cancellation after dispatch must not silently change the order to CANCELLED.
3. Use event_id for idempotency. Replaying an event must not change order or refund state a second time.
4. Use integer paise. Refund amounts must be positive, cannot exceed the outstanding refundable amount, and apply only to eligible cancelled/rejected orders that were paid.
5. Track refund_due_paise and refunded_paise separately. Partial refunds remain partial; set payment status to REFUNDED only when the full due amount has been processed.
6. Reconcile internal and provider summaries by order ID. Report missing records, amount mismatches and status mismatches separately and deterministically.
7. Handle empty input, missing fields, unknown IDs, invalid event types and duplicates without corrupting state.

## Setup
Run: `python -m pip install -r requirements-dev.txt`, then `python -m pytest -q`, then `python -m main`.

## Work to submit
- Read the source and run the starter tests before editing.
- Treat the requirements above as the acceptance contract. Investigate failing tests, trace root causes, and correct the underlying behaviour; do not hard-code fixture output.
- Add regression tests for fixes and document at least five edge cases in `TESTING.md`.
- Submit one pull request against the original repository with code, tests, a root-cause summary and known limitations. Do not merge it.
- Include `ORDER_FLOW_NOTES.md` with one example event sequence, expected states and three edge cases.

## Optional stretch work
Choose at most one after the core behaviours work: export an awaiting-refund CSV report; flag out-of-order events; or summarise orders by state.

## Testing and GitHub Actions
Some visible tests are expected to fail on the untouched starter because key behaviours are incomplete. The exact initial test count is not fixed. GitHub Actions runs against push and pull-request changes and publishes visible test counts. A red check before your fixes is expected. Do not remove, skip, weaken or bypass tests, or edit CI to evade failures.

## Individual-work policy
AI chatbots, AI coding assistants, generated patches/tests and asking another person to write/debug the solution are prohibited. Ordinary non-AI documentation is allowed. Do not upload challenge code/data to external services. You must be able to explain your code and make a small live change if asked. A code walkthrough can support integrity checks, but no automated detector proves whether AI was used.

## Rubric — 100 marks
- Codebase understanding and state-flow explanation: 15
- Root-cause analysis and correctness: 25
- State transitions, idempotency and refund safety: 25
- Regression testing and edge cases: 15
- Code quality and maintainability: 10
- Pull request, notes and live explanation: 10
