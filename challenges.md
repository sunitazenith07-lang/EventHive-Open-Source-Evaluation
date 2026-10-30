# challenges.md - COMPULSORY submission

This file is mandatory and worth 5 marks. Describe your actual experience honestly. Do not invent difficulties to fill the page.

## 1. Challenge or confusing behaviour
The main challenge was understanding incorrect reconciliation results and refund processing.

## 2. Evidence
Initially, ORD-102 was not reported as a status mismatch.

## 3. What I tried
- Inspected service.py.
- Ran the existing tests. 
- Checked reconciliation output.
- Added regression tests for edge cases.

## 4. Resolution
Added separate amount and status comparisons and imporved refund validations.

## 5. Proof and regression prevention
The complete test passed with 218 tests.

## 6. Unresolved challenge or next step
Duplicate order IDs and malformed reconciliation records don not have separate error reporting.