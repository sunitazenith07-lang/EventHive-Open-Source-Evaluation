# Challenges

## 1. The thing that tripped me up

The `True` problem in the refund amount check.

When I saw `True` listed as an invalid refund amount in the test, I thought — okay, `True` is not a number, so my `isinstance(amount, int)` check will block it. Simple.

But it didn't. `True` passed the check and got treated as a valid refund of 1 paise.

I had no idea that in Python, `True` is actually just `1` underneath. `bool` is built on top of `int`, so Python sees `True` as an integer. That was news to me.

---

## 2. Evidence

This test was failing:

```python
def test_invalid_refund_amounts_are_ignored(amount):
    # amount = True in one of the test cases
    result = apply_order_event(order, ev("R", "refund_processed", amount_paise=True))
    assert result["refunded_paise"] == 0  # was failing — got 1 instead
```

I checked in Python directly:

```python
>>> isinstance(True, int)
True
>>> True > 0
True
```

Both passed. So `True` was slipping through as if it were the number `1`.

---

## 3. What I tried

- First I just added `isinstance(amount, int)` and ran the tests — `True` still passed
- Then I printed `type(True)` and saw `<class 'bool'>` — that's when I realised it's a separate type
- I added `isinstance(amount, bool)` as an extra check to block it
- Re-ran the tests and they passed

---

## 4. Resolution

The fix was one extra condition:

```python
if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
    return out
```

The `isinstance(amount, bool)` part specifically catches `True` and `False` before they sneak through the `int` check.

---

## 5. Proof

Tests that now pass because of this fix:
- `test_invalid_refund_amounts_are_ignored[True]`
- `test_invalid_refund_amounts_are_ignored[False]`

A case that could still trip someone up: if a different number type (like one from a data library) is used instead of a plain Python `int`, this check would reject it even if the value looks fine. Not a problem here, but worth knowing.

---

## 6. What I'd look at next

The `None` event_id case. If an event has no `event_id`, the code still processes it and stores `None` in the processed list. A second event with `event_id = None` would then be treated as a duplicate — even if it's a totally different event. I left it as-is because no test covers it, but it's something I'd fix if this were a real project.
