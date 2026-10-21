# OrderOps: Order Failure, Cancellation & Refund Reconciliation

**Track:** Food-delivery operations | **Language:** Python 3.10+ | **Time:** 24-hour evaluation

## Scenario
A food-delivery platform can receive a confirmed payment before the restaurant accepts an order. A restaurant may then reject the order; a customer may cancel before dispatch; and refund notifications can arrive late or more than once. The system must never issue duplicate refunds or claim that an order has been delivered when it has not.

This is a simulated, offline project inspired by common food-delivery workflows. It is not Zomato's internal problem statement or code. Do not call external payment or delivery APIs.

## Required behaviour
1. Process order events without mutating the original order object.
2. Ignore duplicate event IDs after first successful processing.
3. Allow only defined order-state transitions.
4. If a paid order is cancelled before dispatch or rejected by the restaurant, record the appropriate refund due.
5. A refund must be a positive integer amount in paise, cannot exceed the amount due, and can only apply to an order eligible for refund.
6. Mark a refund complete only when the full refundable amount has been processed. Partial refunds must remain visibly partial.
7. Reconcile internal and provider order/payment summaries, reporting missing records and amount/status mismatches deterministically.
8. Handle unknown order IDs, invalid event types, empty input and missing fields without corrupting state.

## Kick-off tasks
Organisers will share three issue tickets at kick-off. Reproduce each issue, explain its root cause, make a focused fix, and add a regression test. Do not guess at ticket details before they are announced.

## Required submission
- A pull request with the fixes and tests.
- `ORDER_FLOW_NOTES.md`: describe the order/payment/refund states, include one example event sequence, and document three edge cases.
- A short explanation of what changed and any known limitations.

## Optional stretch work (choose at most one)
A. Create a deterministic CSV summary of orders awaiting refunds.  
B. Detect events that appear out of order and return an actionable warning.  
C. Add a concise operations summary grouped by order state.

## Testing and workflow
Run `python -m pytest -q`. Initial tests deliberately expose incomplete behaviour. A lower failure count means some defects are fixed; green means all visible tests pass. Every push and pull-request update triggers GitHub Actions against the exact commit. Do not edit workflow files, skip tests, or hard-code fixture output to evade checks.

## Integrity
AI chatbots, code-completion tools, generated patches, generated tests and solution-sharing are prohibited for this evaluation. Ordinary non-AI language/framework documentation is allowed. Do not paste challenge code or data into external services. You must explain the code and make a small live change yourself; the evaluator may ask you to trace a bug and modify its behaviour.

## Rubric — 100 marks
- Codebase understanding and state-flow explanation: 15
- Root-cause analysis and correctness: 25
- State transitions, idempotency and refund safety: 25
- Regression testing and edge cases: 15
- Code quality and maintainability: 10
- Pull request, notes and live explanation: 10
