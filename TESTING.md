# Testing record

Environment: Python 3.14.2. Development dependency: pytest 9.2.0 from requirements-dev.txt.

Commands run:
- python -m pip install -r requirements-dev.txt — installed pytest and its declared dependencies successfully.
- Untouched baseline: python -m pytest -q — **62 failed, 150 passed**.
- After implementation and focused regressions: python -m pytest -q — **215 passed**.
- python -m main — completed successfully and printed the fixture reconciliation results below.
- git diff --check — clean before commit.

## Edge cases covered

| Input / scenario | Expected behavior | Actual result | Test / evidence |
| --- | --- | --- | --- |
| Replay an already processed refund event ID | No second refund is applied | Refunded total stayed at 400 paise after replay | tests/test_regressions.py::test_duplicate_partial_refund_is_idempotent |
| Cancellation requested after dispatch | Remains OUT_FOR_DELIVERY; no cancellation refund is created | Lifecycle acceptance tests passed with the order unchanged | tests/test_acceptance_matrix.py transition cases |
| Refund amount is zero or negative | No refund is recorded | Rejected; refunded_paise remains unchanged | test_refund_must_be_positive and acceptance matrix |
| Refund exceeds outstanding due | Refund is rejected without changing refunded total | Rejected; cumulative refund remains within due | test_refund_cannot_exceed_amount_due and acceptance matrix |
| Partial refund | refunded_paise increases; payment remains PAID until fully refunded | Partial refund remains PAID; full amount changes payment to REFUNDED | refund acceptance tests |
| Equal amount, differing provider status | Report under status_mismatches, not matched | ORD-102 was reported as a status mismatch in the demo | test_reconcile_reports_status_difference and demo |
| Empty internal and provider input | Return empty report lists | All reconciliation lists were empty | test_empty_reconciliation |

Demo output from python -m main:
- missing_from_provider: ORD-103
- missing_from_internal: ORD-104
- amount_mismatches: ORD-101, ORD-102
- status_mismatches: ORD-102

The suite includes the three additional focused regressions in tests/test_regressions.py. No timing or large-dataset benchmark was run.
