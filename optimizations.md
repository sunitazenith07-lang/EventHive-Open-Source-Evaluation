# optimizations.md - Required submission

## 1. Baseline and objective
Improved correctness and maintainability of event processing and reconciliation.


## 2. Options considered
- Check duplicate event IDs before processing.
- Validate refunds against the remaining balance.
- Compare order amounts and statuses separately..

## 3. Changes implemented
- Added duplicate event protection.
- Added refund validation.
- Improved reconciliation logic.

## 4. Trade-offs
The first event with a given IID is accepted. Lter events with same ID are ignored.

## 5. Further improvements
- HAndle duplicate order IDs.
- Add better malformed-record reporting.
- Add persistent event storage.