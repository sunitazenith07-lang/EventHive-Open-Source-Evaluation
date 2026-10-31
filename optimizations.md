# 1. Baseline and objective

- The main issue was correctness, not speed.
- Some events were processed twice, invalid refunds were accepted and reconciliation sometimes gave wrong results.
- Tests showed these problems.

# 2. Options considered

- I decided to add simple checks in the existing code.
- I also thought about rewriting the functions, but avoided it because it would make bigger changes.
- I did not try performance optimization because I didn't find any measured speed issue.

# 3. Changes implemented

- **Change:** Added checks for duplicate events.
- **Reason:** So the same event is not processed again.
- **Tests:** Duplicate event test cases.

- **Change:** Added refund validation.
- **Reason:** To stop invalid or extra refunds.
- **Tests:** Refund amount and eligibility test cases.

- **Change:** Improved reconciliation checks.
- **Reason:** So orders with different statuses are not marked as matched.
- **Tests:** Reconciliation test cases.

- **Measurement:** I did not measure speed or memory improvement.

# 4. Trade-offs

I kept the changes small and used basic conditions instead of rewriting everything. This made the code easier to understand and reduced unnecessary changes.

# 5. Further improvements

If I get more time, I would add more edge case tests and check performance with larger data. If it is actually slow, then I would try to optimize it.