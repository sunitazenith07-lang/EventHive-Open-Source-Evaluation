# approach.md — Engineering Approaches in OrderOps

This document explains the technical problems, thought processes, and engineering approaches used to build and fix the **OrderOps** system. It is written in simple, clear language for anyone with basic Python knowledge.

---

## 1. Project Overview & Order-Processing Flow

**OrderOps** is a simulated backend engine for food delivery platforms (like Zomato or Swiggy). It manages what happens to an order from the moment a customer clicks "Place Order" to when it is delivered or cancelled, tracks payment and refund amounts, and checks if internal database records match external bank records.

### The Big Picture: How an Event Moves Through the System

When something happens in the real world (for example, a customer pays, a restaurant accepts the food ticket, or a driver delivers the food), that action is sent to the backend as a dictionary called an **event**.

The entire order-processing flow works in five clean steps:

1. **Receiving the Input**:
   - The function `apply_order_event(order, event)` receives the current `order` dictionary and the new `event` dictionary.
2. **Making a Safe Copy (Immutability)**:
   - We use Python's `copy.deepcopy(order)` so we never change or accidentally corrupt the caller's original data.
3. **The Security Gate (Idempotency Check)**:
   - We look at `event_id`. If this exact event was already processed in the past, we immediately return the order copy without touching anything.
4. **Applying Domain Logic (State Machine & Refunds)**:
   - If the event is new, the code checks its `type` (for example, `restaurant_accepted`, `cancel_requested`, `refund_processed`) and verifies whether the order is allowed to make that transition.
   - If allowed, the order status and financial counters (`payment_status`, `refund_due_paise`, `refunded_paise`) are updated.
5. **Audit Logging & Return**:
   - The `event_id` is appended to `processed_event_ids` to remember it for the future.
   - The updated order dictionary is returned.

Later, when auditing books at the end of the day, `reconcile_orders(internal, provider)` compares company records with bank records to find missing entries, price differences, or mismatched order statuses.

---

## 2. Problem-by-Problem Approaches

---

### Problem 1: Event Replay & Preventing Duplicate Processing (Idempotency)

- **Problem:**
  Network connections on mobile phones and payment gateways frequently disconnect and retry. A payment gateway might send the exact same webhook event (`{"event_id": "EV-101", "type": "payment_confirmed"}`) three times. In the starter code, the function processed the event all three times and added `"EV-101"` to the list three times (`["EV-101", "EV-101", "EV-101"]`). If this were a refund event, the customer would get paid three times!
- **Approach:**
  We added an upfront check at the very top of `apply_order_event`:
  ```python
  if event_id and event_id in out["processed_event_ids"]:
      return out
  ```
  If `event_id` is already in `processed_event_ids`, we stop right there and return the existing order state immediately.
- **Why this approach?**
  It provides an immediate, safe exit (known as "short-circuiting"). The rest of the state machine never runs on duplicates, preventing duplicate state changes, duplicate money transfers, and list pollution.
- **Example:**
  - *Order before event:* `processed_event_ids: ["EV-01"]`
  - *Incoming event:* `{"event_id": "EV-01", "type": "payment_confirmed"}`
  - *Result:* Found `"EV-01"` in the list $\rightarrow$ return order as-is.

---

### Problem 2: Order State Transitions & Post-Dispatch Protection

- **Problem:**
  An order cannot jump to any random state. For example, if a delivery driver is already driving to your house (`OUT_FOR_DELIVERY`), you should not be able to cancel the order. In the starter code, cancellations were partially guarded, but transitions needed strict validation to prevent impossible paths (like accepting an order that was already rejected).
- **Approach:**
  We set up explicit conditions for each event type:
  - `restaurant_accepted` only works if the order is currently `PLACED`.
  - `restaurant_rejected` only works if the order is currently `PLACED`.
  - `cancel_requested` only works if the order is currently `PLACED` or `ACCEPTED`. If the status is `OUT_FOR_DELIVERY` or `DELIVERED`, the cancellation request is safely ignored.
  - `dispatch_started` only works if the order is `ACCEPTED`.
  - `order_delivered` only works if the order is `OUT_FOR_DELIVERY`.
- **Why this approach?**
  This turns our code into a predictable **Finite State Machine**. Every state transition has a clear prerequisite, protecting restaurant food preparation and driver effort from invalid actions.
- **Example:**
  - *Current status:* `OUT_FOR_DELIVERY`
  - *Incoming event:* `{"event_id": "C1", "type": "cancel_requested"}`
  - *Result:* Because current status is not `PLACED` or `ACCEPTED`, the status remains `OUT_FOR_DELIVERY`.

---

### Problem 3: Refund Eligibility Validation

- **Problem:**
  In the starter code, whenever an event of type `refund_processed` arrived, the service blindly added the refund amount to `refunded_paise`. An active delivery in `OUT_FOR_DELIVERY` or an unpaid order could receive a refund!
- **Approach:**
  We introduced a strict three-part eligibility rule (`is_eligible`):
  1. The order status must be either `REJECTED` or `CANCELLED`.
  2. The payment status must be `PAID`.
  3. The money owed (`refund_due_paise`) must be greater than zero (`> 0`).
  If any of these three conditions is missing, the refund event is completely ignored.
- **Why this approach?**
  A platform should only refund money if two facts are true: we actually took the customer's money (`PAID`), and we failed to fulfill the order (`REJECTED` or `CANCELLED`). An order that was delivered successfully should never be automatically refunded by a lifecycle webhook.
- **Example:**
  - *Order:* Status `DELIVERED`, Payment status `PAID`, Refund due: `0`.
  - *Incoming event:* `{"type": "refund_processed", "amount_paise": 5000}`.
  - *Result:* Status is `DELIVERED` (not `REJECTED` or `CANCELLED`) $\rightarrow$ Ineligible. Refunded amount stays `0`.

---

### Problem 4: Strict Refund Amount Validation & The Python Boolean Trap

- **Problem:**
  What if an external system sends an invalid refund amount, such as a negative number (`-500`), zero (`0`), a string (`"500"`), a float (`50.5`), or a boolean flag (`True`)? The starter code did `out["refunded_paise"] += event.get("amount_paise", 0)`, which allowed invalid data types to corrupt the balance.
  In Python, there is a hidden trap: `isinstance(True, int)` returns `True` because `bool` is a subclass of `int`! If someone passes `amount_paise: True`, Python treats it as 1 paisa!
- **Approach:**
  We used strict type and sign checks:
  ```python
  type(amt) is int and amt > 0
  ```
  Using `type(amt) is int` specifically checks for pure integer numbers and rejects boolean values (`True` or `False`). We also check `amt > 0` to make sure zero and negative numbers are rejected.
- **Why this approach?**
  Money cannot be negative, zero, fractional, or a boolean flag. Enforcing strict integer types prevents financial calculation errors.
- **Example:**
  - *Incoming amount:* `True` $\rightarrow$ `type(True) is int` evaluates to `False` $\rightarrow$ Rejected.
  - *Incoming amount:* `-500` $\rightarrow$ `amt > 0` evaluates to `False` $\rightarrow$ Rejected.
  - *Incoming amount:* `500` $\rightarrow$ `type(500) is int` and `500 > 0` are both `True` $\rightarrow$ Accepted.

---

### Problem 5: Preventing Refunds Greater than Amount Due (Upper Bound Cap)

- **Problem:**
  Suppose an order total is ₹50 (5000 paise). If the platform receives two refund events of ₹30 (3000 paise) and ₹40 (4000 paise), the total refunded would be ₹70 (7000 paise). The platform would lose ₹20 of its own money!
- **Approach:**
  We added a cumulative ceiling check:
  ```python
  out["refunded_paise"] + amt <= out.get("refund_due_paise", 0)
  ```
  If adding the new refund would push the total refunded paise above `refund_due_paise`, the event is rejected, and `refunded_paise` is not changed.
- **Why this approach?**
  It is a hard financial safety barrier. A customer can never receive more money back than what was originally due on their cancelled order.
- **Example:**
  - *Refund due:* `5000` paise. *Already refunded:* `3000` paise.
  - *Incoming refund:* `3000` paise.
  - *Calculation:* `3000 + 3000 = 6000`, which is greater than `5000` $\rightarrow$ Rejected!

---

### Problem 6: Handling Partial vs. Full Refunds Correctly

- **Problem:**
  In the starter code, line 40 checked:
  ```python
  if out["refunded_paise"] >= out.get("refund_due_paise", 0):
      out["payment_status"] = "REFUNDED"
  ```
  If `refund_due_paise` was `0` on an unpaid order, evaluating `0 >= 0` was `True`, falsely changing the payment status to `"REFUNDED"`. Furthermore, when a partial refund was processed, we had to ensure the order stayed `"PAID"` until the entire debt was paid.
- **Approach:**
  We made the status change condition exact:
  ```python
  if out["refunded_paise"] == out.get("refund_due_paise", 0):
      out["payment_status"] = "REFUNDED"
  ```
  Because the eligibility rule already guarantees that `refund_due_paise > 0`, the payment status only changes to `"REFUNDED"` when the refunded amount exactly reaches 100% of the due amount. Until then, it stays `"PAID"`.
- **Why this approach?**
  It prevents partial refunds from being marked as finished, and prevents unpaid orders from being marked as refunded.
- **Example:**
  - *Refund due:* `1000` paise.
  - *First refund:* `400` paise $\rightarrow$ `refunded_paise = 400`. `400 != 1000`, so status stays `"PAID"`.
  - *Second refund:* `600` paise $\rightarrow$ `refunded_paise = 1000`. `1000 == 1000`, so status becomes `"REFUNDED"`.

---

### Problem 7: Late Payment Arrival After Cancellation or Rejection

- **Problem:**
  Imagine you place an order. Your internet lags, so the payment confirmation webhook is delayed. In the meantime, the restaurant runs out of food and rejects the order (`status: REJECTED`, `payment_status: UNPAID`). Because it was unpaid when rejected, `refund_due_paise` was set to `0`.
  Ten seconds later, the delayed payment confirmation arrives: `payment_confirmed`. In the starter code, `payment_status` was changed to `"PAID"`, but `refund_due_paise` stayed `0`. The customer paid for an unfulfilled order, but the system recorded ₹0 owed!
- **Approach:**
  Inside the `payment_confirmed` branch, we added an extra check:
  ```python
  if kind == "payment_confirmed":
      out["payment_status"] = "PAID"
      if out.get("status") in ("REJECTED", "CANCELLED"):
          out["refund_due_paise"] = out.get("total_paise", 0)
  ```
  If payment confirms on an order that was already rejected or cancelled, we immediately record `refund_due_paise = total_paise`.
- **Why this approach?**
  It ensures accounting consistency regardless of whether payment arrives before or after cancellation/rejection.
- **Example:**
  - *Order rejected while unpaid:* `status: "REJECTED"`, `payment_status: "UNPAID"`, `refund_due_paise: 0`.
  - *Payment arrives later:* `payment_status` becomes `"PAID"`, and `refund_due_paise` immediately becomes `total_paise` (e.g. 5000 paise). The customer is now properly eligible for their refund.

---

### Problem 8: Reconciliation & Field Name Normalization (`total_paise` vs `amount_paise`)

- **Problem:**
  When comparing our company database (`internal`) with bank settlement files (`provider`), we found that internal orders created by `models.py` store price under the key `"total_paise"`, but provider records store price under `"amount_paise"`.
  In the starter code, `reconcile_orders` searched exclusively for `a.get("amount_paise") != b.get("amount_paise")`. For internal orders, `a.get("amount_paise")` returned `None`. Because `None != 45900`, every internal order in `main.py` was falsely reported as an amount mismatch!
- **Approach:**
  We introduced a helper function inside `reconcile_orders`:
  ```python
  def _get_amount(record: dict):
      if "amount_paise" in record:
          return record.get("amount_paise")
      return record.get("total_paise")
  ```
  This helper checks for `"amount_paise"` first, and if that is missing, it falls back to `"total_paise"`.
- **Why this approach?**
  It normalizes the data cleanly without modifying the original input records, allowing different naming conventions across systems to be compared seamlessly.
- **Example:**
  - Internal order: `{"order_id": "ORD-101", "total_paise": 45900}` $\rightarrow$ amount extracted: `45900`.
  - Provider record: `{"order_id": "ORD-101", "amount_paise": 45900}` $\rightarrow$ amount extracted: `45900`.
  - Result: `45900 == 45900` $\rightarrow$ Amounts match!

---

### Problem 9: Handling Status Mismatches in Reconciliation

- **Problem:**
  In the starter code, line 62 had a comment: `# Deliberate starter defect: mismatched statuses may be called matched.`
  If the transaction amounts matched, the starter code immediately added the order to `report["matched"]` without checking if the order statuses matched. An order that was marked `ACCEPTED` internally but `CANCELLED` by the provider was incorrectly called a match!
- **Approach:**
  We split the comparison into a clear hierarchy:
  1. If amounts do not match $\rightarrow$ add to `report["amount_mismatches"]`.
  2. If amounts match, but statuses do not match $\rightarrow$ add to `report["status_mismatches"]`.
  3. If both amounts and statuses match $\rightarrow$ add to `report["matched"]`.
- **Why this approach?**
  Financial reconciliation requires both financial agreement (amounts) and operational agreement (order status). Isolating status differences prevents operational discrepancies from being swept under the rug.
- **Example:**
  - `ORD-102` has amount 129900 paise on both sides.
  - Internal status: `ACCEPTED`. Provider status: `CANCELLED`.
  - Result: Amounts match, but statuses differ $\rightarrow$ Placed into `status_mismatches: ["ORD-102"]`.

---

### Problem 10: Event ID Sanitization and Invalid Input Handling

- **Problem:**
  What happens if an event has no ID at all (`event_id = None` or `""`), or has an unrecognized event type (like `"unknown"` or `"chargeback"`)? In the starter code, line 43 unconditionally ran `out["processed_event_ids"].append(event_id)`, which added `None` into our clean list of string IDs (`[None]`).
- **Approach:**
  1. We only append event IDs if they are valid and truthy:
     ```python
     if event_id:
         out["processed_event_ids"].append(event_id)
     ```
  2. If an event has an unknown type, none of our `if/elif` branches trigger. The function safely falls through, leaving order status and balances untouched.
- **Why this approach?**
  It keeps our audit log clean and guarantees that unrecognized or malformed events do not crash the system or corrupt data.
- **Example:**
  - Incoming event: `{"event_id": "U1", "type": "some_random_event"}`.
  - Result: Order status stays `PLACED`, balances stay `0`, and only `"U1"` is safely recorded in `processed_event_ids`.

---

## 3. Important Technical Decisions Explained Simply

1. **Why Pure Functions and Deepcopy?**
   In Python, dictionaries are passed by reference. If function $A$ changes a dictionary, function $B$ sees that change. By using `deepcopy(order)` at the start of `apply_order_event`, we ensure the original order is never modified in place. If an event turns out to be invalid or ineligible, we can safely discard or return without side effects.
2. **Why Integer Paise Instead of Floats?**
   Computers store floating-point numbers in binary, which leads to tiny rounding errors (for example, `0.1 + 0.2` in Python equals `0.30000000000000004`). In banking and e-commerce, rounding errors lead to lost pennies and audit failures. By storing all currency as **integer paise** ($₹1.00 = 100\text{ paise}$), all math is exact: $100 + 200 = 300$.
3. **Why Use a List for `processed_event_ids` Instead of a Set?**
   A Python `set` has faster lookups, but its items have no guaranteed order and cannot be directly saved to standard JSON. A Python `list` preserves the exact chronological order of events and matches the repository test assertions. Because each food order only handles 5 to 10 events on average, checking `event_id in list` takes virtually zero time.
4. **Why Set Union for Reconciliation?**
   In `reconcile_orders`, we need to compare all order IDs from both systems. Instead of using nested `for` loops (which would be slow for thousands of orders), we do `sorted(set(left) | set(right))`. The pipe symbol `|` takes the mathematical union of both sets in linear time, ensuring our reconciliation runs fast even on large datasets.

---

## 4. Verification Evidence

All approaches described in this document have been verified through actual test and demo runs:
- **Test Suite**: Executing `python -m pytest -q` passes all **212 tests** (12 contract tests in `test_contract.py` and 200 parameterized matrix tests in `test_acceptance_matrix.py`) in **0.32 seconds**.
- **Offline Demo**: Executing `python -m main` produces the exact expected reconciliation output:
  ```text
  matched: ['ORD-101']
  missing_from_provider: ['ORD-103']
  missing_from_internal: ['ORD-104']
  amount_mismatches: []
  status_mismatches: ['ORD-102']
  ```
- **Large Dataset**: Running `reconcile_orders` against `data/records.json` (150 orders vs 163 provider records) successfully categorizes all records: 107 matched, 12 missing from provider, 25 missing from internal, 20 amount mismatches, and 11 status mismatches.
