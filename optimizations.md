# optimizations.md - Required submission

## 1. Baseline and objective
Improved correctness and maintainability of event processing and reconciliation.


## 2. Options considered
- Check duplicate event IDs before processing.
- Validate refunds against the remaining balance.
- Compare order amounts and statuses separately..

## 3. Changes implemented
- Added safe handling of malformed reconciliation records.
- Added integer type validation for reconciliation amounts.
- Used deterministic sorting for reconciliation results.
- Kept reconciliation output structure unchanged to preserve compatibility.

## 4. Trade-offs
The first event with a given IID is accepted. Lter events with same ID are ignored.

## 5. Further improvements
Work Done