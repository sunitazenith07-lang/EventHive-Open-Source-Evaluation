# Optimizations

## 1. Baseline and objective

My main goal was to ensure the system was reliable first. I ran the tests and they finished in under a second (around 0.68s for 212 tests), which is plenty fast for the current dataset. I didn't see any obvious lag or memory spikes, so I focused on correctness over raw speed.

## 2. Options considered

I thought about a few ways to make it faster:
- **Event Tracking**: Right now, `processed_event_ids` is a list. Checking if an ID is in a list takes longer as the list grows (O(n)). I considered changing this to a `set`, which would make lookups nearly instant (O(1)).
- **Reconciliation**: The current dictionary-based approach for matching orders is already quite efficient for the number of orders we're dealing with. I thought about more complex sorting algorithms, but that would just make the code harder to read without providing a real speed boost.

## 3. Changes implemented

I decided **not** to implement any performance changes. 

**Reason**: In a real project, you shouldn't optimize code that isn't slow. Adding a `set` for event tracking would make the code slightly more complex to maintain, and since the event history for a single order is usually small, the speed difference is negligible. I'd rather have code that is easy to debug than code that is 0.001s faster.

## 4. Trade-offs

By sticking with the list for event history, I keep the events in the order they arrived, which is helpful for debugging. The trade-off is that if an order had thousands of events, the `if event_id in order.get(...)` check would slow down. However, for typical order lifecycles, this is a non-issue.

## 5. Further improvements

If this ever needs to scale to millions of orders, the first thing I'd do is move the data out of memory and into a database (like PostgreSQL). I'd also implement a proper profiling step using `cProfile` to find actual bottlenecks before guessing where the slowness is. Only then would I switch the event tracking to a set or introduce a more advanced reconciliation strategy.
