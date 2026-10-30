# challenges.md - OrderOps investigation record

AI assistance was used during this work. Check the current evaluation policy before submitting; this file does not claim individual, no-AI authorship.

## 1. Challenge
The first checkout was a GitHub VFS workspace, while Git and tests required a local clone. The VFS edits were not present in the clean local clone, so the changes had to be reapplied on a feature branch.

## 2. Evidence
- The local clone started clean on `main` and its `service.py` still contained the starter defects.
- Baseline pytest: 62 failed, 150 passed.
- Failing assertions included duplicate event IDs, invalid refund mutations, and status mismatches reported as matched.

## 3. What I tried
- Read the starter implementation and both test files.
- Ran the baseline suite and demo in the local clone.
- Reproduced behavior using existing acceptance tests, then added targeted regressions.

## 4. Resolution
The service did not check event IDs before applying them, accepted unchecked refund values, and omitted provider/internal status comparison. The fix validates event/refund inputs and compares both reconciliation fields.

## 5. Proof and regression prevention
The final suite passed 219 tests. New coverage checks duplicate refunds, malformed events, amount-plus-status mismatches, and full refund completion after partial processing.

## 6. Remaining challenge
Repeated rows with the same order ID still resolve to the last row in the existing dictionaries. No duplicate-summary policy was specified or added; define one and add tests if such rows are valid input.