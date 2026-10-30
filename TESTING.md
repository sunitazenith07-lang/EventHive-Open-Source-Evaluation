# Testing record

Environment: Python 3.14.2. Development dependency: pytest 9.2.0 from requirements-dev.txt.

Commands run:
- python -m pip install -r requirements-dev.txt — installed pytest and its declared dependencies successfully.
- Untouched baseline: python -m pytest -q — **62 failed, 150 passed**.
- After implementation: python -m pytest -q — **212 passed before adding three focused regression tests; final result after adding them: 215 passed.**.
- python -m main — executed after implementation; see demo result below.

## Edge cases covered

| Input / scenario | Expected behavior | Evidence |
| --- | --- | --- |
| Replay an already processed event ID | No second state or refund change | tests/test_contract.py idempotency coverage; acceptance matrix |
| Cancellation requested after dispatch | Remains OUT_FOR_DELIVERY; no cancellation refund is created | transition tests in tests/ |
| Refund amount is zero or negative | No refund is recorded | test_refund_must_be_positive and acceptance matrix |
| Refund exceeds outstanding due | Refund is rejected without changing refunded total | test_refund_cannot_exceed_amount_due and acceptance matrix |
| Partial refund | refunded_paise increases; payment remains PAID until fully refunded | refund acceptance tests |
| Equal amount, differing provider status | Report under status_mismatches, not matched | test_reconcile_reports_status_difference |
| Empty internal and provider input | Return empty report lists | test_empty_reconciliation |

Demo result: python -m main completed and printed reconciliation lists. It reported ORD-103 missing from provider, ORD-104 missing from internal, amount mismatches ORD-101 and ORD-102, and status mismatch ORD-102. This is the demo fixture output.
