# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
- Ran 'python -m pytest -q'
- Initial test result: 150 passed, 62 failed.
- Ran 'python -m main' to check reconciliation output.

## 2. Codebase understanding
- 'service.py': order events and reconciliation.
- 'models.py': order structure.
- 'fixtures.py': sample data.
- 'main.py': demo execution.
- 'tests/': expected behaviour.

## 3. Investigation and implementation strategy
For each major defect, describe the observed symptom, the hypothesis you tested, evidence from a test/log/example, and the fix chosen.
- Issue 1: Duplicate and invalid events were not handled properly.
- Issue 2: Refund validation allowed unsafe amounts.
- Issue 3: Reconciliation did not correctly compare order statuses and amount fields.

## 4. Implementation decisions
- Added event ID and event type validation.
- Added duplicate event protection.
- Added refund eligibility and amount validation.
- Added cumulative refund limit.
- Corrected amount and status reconciliation.

## 5. Verification
- Added 6 regression tests.
- Latest result: 218 tests passed.
- Verified the offline demo using 'python -m main'.
- Remaining failures or known limitations:

Record actual engineering decisions and evidence. Do not claim tests or experiments you did not run.