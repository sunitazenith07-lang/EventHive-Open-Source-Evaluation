# 1. Baseline

- **Commands run before editing:** `python3 -m pytest -v`
- Initial test result: [Insert actual test summary prior to editing here]
- We looked at the demo/output regarding the processing of order events and the behaviour of order reconciliation. The main areas that we examined were duplicate events, refund validation, changes to payment status and reconciliation mismatches.

# 2. Codebase understanding

The key files and functions that were looked at included service.py, with a special focus on the apply_order_event() and reconcile_orders() functions; the order model and its related tests were also examined.
The order lifecycle and data flow are followed using order receive events (these update the order status and the payment details) and refund events (these update the amount that has been refunded). Reconciliation is carried out based on the provider's records.
– The way I checked my understanding was to run the test suite and use the failing tests to identify the incorrect behaviour and to verify the changes.

# 3. Strategy for the investigation and implementation

- In issue 1, there was a risk of the same event ID being processed more than once; checks have therefore been added to make sure that an event ID which is missing or which has already been processed is not handled.

- In issue 2, refunds were sometimes given for orders that were not eligible or for amounts that were invalid. Before updating the refund total, we checked the order status, the payment status, the amount as a positive integer, and the refund limit.

- Issue 3: Wrong reconciliation. It was possible to reconcile orders that had the same amount but different statuses. The comparison has now been altered so that both the amount and the status must be the same.

# 4. Implementation decisions

- The main changes and the reasons for them are that validation checks have been added before the order data is altered, refunds have been made sure are not greater than the amount due, and the reconciliation checks have been made more stringent.
- The alternatives that were considered and the reasons why they were rejected: We decided not to rewrite all of the functions. Instead, we have retained the existing structure and have simply used basic if statements and loops so that the changes could be as easy to follow as possible.
- It is assumed that refunds apply only in cases where an order has been rejected or cancelled and that the amount of the refund must be a positive integer, not exceeding the refund due.

# 5. Verification

- When adding or modifying tests, you must list the specific test files or cases that have been added or changed. If all you have done is re-run the existing tests, you should not state that you have added new tests.
- The commands were executed and the results obtained: the command 'python3 -m pytest -v' was run. In earlier test runs it had shown '211 passed, 1 failed' and then '205 passed, 7 failed' following the additional changes. These are the temporary results, not the final result.
- The edge cases, such as duplicates involving the event ID, refund eligibility, refund limits, and invalid refund amounts, were all taken into account by the failing tests as part of the investigation.
- Further failures or known limitations: Make sure to verify the most recent test result before submitting it. Do not state that all the tests have passed until the final run has done so.