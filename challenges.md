# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour

The challenge was a silent misclassification: an order whose internal and provider records had the same amount but different statuses was reported as `matched`. Nothing failed or raised an error, so the report looked correct unless the statuses were compared.

## 2. Evidence

The original test suite produced:

```text
62 failed, 150 passed
```

The test that exposed the problem:

- `test_reconciliation_status_mismatch_matrix`

It showed that records with different statuses could appear in the `matched` list.

[FILL IN: paste the failing assertion output you saw for this test, if you have it.]

## 3. What I tried

1. Ran `python -m pytest -q` and `pytest -x -vv` to see the reconciliation failures.
2. Examined `reconcile_orders()` in `service.py`.
3. Found that the code checked the amount and then classified the order as matched without comparing the status.
4. Added a status comparison after the amount comparison, reporting differences under `status_mismatches`.
5. Re-ran the reconciliation test and then the full suite.

## 4. Resolution

- Root cause: `reconcile_orders()` decided an order was matched after comparing only the amount.
- What changed: a status comparison was added, so an order is `matched` only when both amount and status are equal.
- Why it addresses the cause: orders with equal amounts but different statuses now go to `status_mismatches`.

## 5. Proof and regression prevention

- Targeted reconciliation status mismatch test: [FILL IN]
- Final full suite: 212 passed in 3.57 seconds.
- No test files were modified.

Related cases that could still break:
- An order where both amount and status differ (only the amount mismatch is reported).
- Records with a missing status or amount field, since the comparison uses `.get()`.

## 6. Unresolved challenge or next step

When both amount and status differ for the same order, the `if`/`elif` structure records only the amount mismatch. A next step is to decide whether reconciliation should report both, and to write a focused test for that case before changing the code.