# Optimizations

## 1. What I looked at and why

After getting all the tests to pass, I took a step back and looked at the code again — not to fix bugs this time, but to see if anything could be written in a cleaner or smarter way.

There were two things that stood out to me:

**Thing 1 — The idempotency check uses a list.**

The `processed_event_ids` is a Python list. Every time a new event comes in, the code does:

```python
if event_id in out["processed_event_ids"]:
```

This works fine. But in Python, checking "is this item in a list?" means it goes through the list one by one from the start until it finds a match. If the list has 1000 event IDs, it might check all 1000 before saying "yes, it's there."

**Thing 2 — The reconcile function reads both lists twice.**

In `reconcile_orders`, the code builds two dictionaries (`left` and `right`) from the input lists, then loops through all the keys. This is already pretty efficient. But I wondered if there was a simpler way.

---

## 2. Options I thought about

### Option A — Change `processed_event_ids` from a list to a set

A **set** in Python is like a list, but looking things up in it is much faster. Instead of checking one by one, it jumps straight to the answer.

With a list:
```python
# Slow for large lists — checks each item one by one
if event_id in ["e1", "e2", "e3", "e4", ...]
```

With a set:
```python
# Fast — doesn't matter how many items are in it
if event_id in {"e1", "e2", "e3", "e4", ...}
```

**Risk:** The tests check that `processed_event_ids` is a list (e.g., `assert result["processed_event_ids"] == ["e1"]`). If I change it to a set, those tests would fail because sets don't have order and look different from lists.

So I **did not change this**. Correctness comes first. The speed difference only matters if you have thousands of events per order anyway, which isn't the case here.

---

### Option B — Use early returns to avoid deeply nested code

This one I **did actually do** while fixing the bugs.

The original `refund_processed` block would have needed multiple nested `if` checks inside each other, like this:

```python
# The messy way — hard to read
elif kind == "refund_processed":
    if order is eligible:
        if amount is valid:
            if amount doesn't exceed limit:
                # finally do the refund
```

Instead, I used early returns — check one condition at a time, and exit immediately if it fails:

```python
# The cleaner way — easy to read
if not eligible:
    return out

if not valid amount:
    return out

if exceeds limit:
    return out

# All good — do the refund
```

This doesn't make the code faster really, but it makes it much easier to read and understand. Each check is on its own line, in plain view. You don't have to count brackets or track indentation.

---

### Option C — Combine the amount and status mismatch checks into one line

In `reconcile_orders`, I could have written the check as one condition:

```python
if a.get("amount_paise") != b.get("amount_paise") or a.get("status") != b.get("status"):
    # something is wrong
```

But this loses information — you can't tell if it was the amount or the status that didn't match. The tests need them reported separately. So I kept them as two separate `if/elif` checks.

---

## 3. Changes I actually made

### Change 1 — Early returns in the refund block

**What I changed:** Instead of nested `if` statements inside the `refund_processed` block, I wrote a series of guard checks that each return early if a condition fails.

**Why:** It's easier to read. Each rule (eligibility, valid amount, no overflow) is clearly visible on its own. If someone reads this code 6 months later, they can understand each rule in one glance.

**Tests protecting this:**
- `test_refund_requires_eligible_order`
- `test_refund_must_be_positive`
- `test_refund_cannot_exceed_amount_due`
- `test_partial_refund_is_not_marked_complete`

**Did I measure speed?** No. For this exercise there's no need — the data is tiny and the logic runs in microseconds either way. Measuring it would be overkill.

---

### Change 2 — Idempotency check placed at the very top

**What I changed:** The duplicate event check (`if event_id in processed_event_ids`) is now the first thing that runs after setting defaults — before any state transition logic.

**Why:** If an event is a duplicate, there's zero reason to run any of the code below it. Putting the check at the top means the function exits immediately for duplicates, without touching any `if/elif` branches. It also makes the logic easier to follow — "step one: is this a duplicate? if yes, stop."

**Tests protecting this:**
- `test_duplicate_event_is_idempotent`
- `test_payment_event_replay_idempotent` (20 cases)

---

## 4. Trade-offs

The biggest trade-off I made was **keeping `processed_event_ids` as a list** even though a set would be technically faster for lookups.

Here's the honest comparison:

| | List | Set |
|---|---|---|
| Lookup speed | Slower (checks one by one) | Faster (direct lookup) |
| Preserves order | Yes | No |
| Tests pass | Yes | No — tests expect a list |
| Right choice here | ✅ Yes | ❌ No |

For this project the list is fine. Orders don't realistically have thousands of events. If this were a real system processing millions of orders with hundreds of events each, switching to a set (while keeping a separate list for display purposes) would make sense — but that's a problem for a much bigger system.

The main priority was always: **correct first, then clean, then fast**.

---

## 5. What I'd improve next if I had more time

**Idea 1 — Validate `event_id` at the start**

Right now, if an event comes in with `event_id = None` or `event_id = ""`, the code accepts it. That could cause weird bugs. A simple check like:

```python
if not event_id or not isinstance(event_id, str):
    return out  # reject events with no proper ID
```

would make the system more reliable.

**Idea 2 — Add a timestamp to events**

Currently there's no way to tell if events are arriving out of order. In a real food delivery app, sometimes the network is slow and events arrive late. A `timestamp` field on each event would let us detect when something happened out of order (like a `dispatch_started` arriving before `restaurant_accepted`).

I'd add an `event_timestamp` field and log a warning (not crash) when things look out of order.

**Idea 3 — Cleaner error reporting instead of silent ignores**

Right now, invalid events (wrong status, bad amount, duplicate) are silently dropped. The function just returns the unchanged order. That's safe, but if you're debugging and something isn't working, you have no idea why.

A small improvement would be to return a second value — like a reason string — that tells the caller what was rejected and why. Something like:

```python
return out, "refund_rejected: amount exceeds remaining due"
```

That would make debugging much easier without changing any of the core logic.
