# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour

The hard part of this bug was that nothing visibly broke. An order with the same amount but a different status on each side was reported as `matched`, with no error, so the report looked fine unless the statuses were compared.

## 2. Evidence

The original test suite produced:

```text
62 failed, 150 passed
```

The test that pointed to this problem:

- `test_reconciliation_status_mismatch_matrix`

It showed that records with different statuses could appear in the `matched` list.

[FILL IN: paste the failing assertion output you saw for this test, if you have it.]

## 3. What I tried

1. Ran `python -m pytest -q` and `pytest -x -vv` to look at the reconciliation failures.
2. Read `reconcile_orders()` in `service.py`.
3. Found that the code compared the amount and then marked the order as matched without looking at the status.
4. Added a status comparison after the amount comparison, so differences go to `status_mismatches`.
5. Re-ran the reconciliation test, then the full suite.

## 4. Resolution

- Root cause: `reconcile_orders()` treated an order as matched after comparing only the amount.
- What changed: a status comparison was added, so an order is `matched` only if both its amount and its status are equal.
- Why this fixes the cause: orders with equal amounts but different statuses are now sent to `status_mismatches`.

## 5. Proof and regression prevention

- Targeted reconciliation status mismatch test: [FILL IN]
- Final full suite: 212 passed in 3.57 seconds.
- No test files were modified.

Related cases that could still break:
- An order where both amount and status differ: only the amount mismatch is reported.
- Records with a missing amount or status field, since the comparison uses `.get()`.

## 6. Unresolved challenge or next step

For an order where both amount and status differ, the `if`/`elif` structure records only the amount mismatch. As a next step I would decide whether both should be reported, and write a focused test for that case before changing the code.
