# Project notes

## Requirements completed
- Ran the baseline and investigated `service.py`, `models.py`, `fixtures.py`, `main.py` and the tests.
- Fixed duplicate event processing, refund validation, refund eligibility and reconciliation status mismatches.
- Added `tests/test_my_regressions.py` (14 tests).
- Completed the documentation files.

## Files changed and why
- `service.py`: event processing, refund and reconciliation fixes.
- `tests/test_my_regressions.py`: new regression tests; no existing test file was modified.
- Documentation `.md` files.
- Review before submitting: `eventhive_evaluation_starter.egg-info/` appeared in the Git diff and probably should not be committed.

## Tests run
Python 3.13.7, pytest 9.2.0.
- Initial: 62 failed, 150 passed.
- Targeted idempotency: 20 passed. Refund eligibility matrix: 12 passed.
- After my first 6 new tests: 4 failed, 214 passed (wrong event key in my test helper).
- Final `python -m pytest -q`: 226 passed.
- `python -m main` ran and printed the reconciliation report.

## Assumptions
- Event IDs identify events processed once; refund amounts are integer paise.
- Refunds only for paid `REJECTED`/`CANCELLED` orders, up to the remaining due.
- Reconciliation matches by `order_id`.

## Known limitations
- If both amount and status differ, only the amount mismatch is reported.
- Events with no `event_id` after the first are treated as duplicates.
- An invalid refund still records its event ID.
- No performance benchmarks were run.

## AI assistance
AI tools were used for explanation, debugging help and drafting tests and documentation, with the administrator's permission. Confirm the exact declaration wording with the administrator before submitting.