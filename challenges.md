# OrderOps Engineering Challenges & Debugging Log

> **Author:** Shubham Kumar
> **Repository:** `OrderOps-Open-Source-Evaluation`
> **Evaluation Component:** Compulsory Problem-Solving Documentation (5 Marks — COMPULSORY)
> **Document Purpose:** Honest, detailed engineering log documenting concrete technical obstacles, reproducible failure evidence, false assumptions disproven, and technical resolutions implemented.

---

## Conflict & Pre-existing File Notice
This file replaces the starter prompt template `challenges.md` (23 lines of instructional placeholders) with the completed engineering submission as required by `STUDENT_PROBLEM_STATEMENT.md`.

---

## 1. Challenge 1: The Python Boolean Subclass Trap in Monetary Validation

### Initial Symptoms
During test execution of `test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]`, the test failed with:
```text
AssertionError: assert 1 == 0
  + where 1 = result["refunded_paise"]
```
Passing boolean `True` in `amount_paise` unexpectedly incremented the order's `refunded_paise` by 1.

### Root Cause
In Python, `bool` is a direct subclass of `int` (`issubclass(bool, int) == True`). When performing standard type validation using `isinstance(value, int)`, a boolean `True` evaluates to `True` and has an integer value of `1`. The starter code checked `isinstance(amount, int) and amount > 0`, causing `True` to pass as a valid 1-paisa refund.

### Investigation Steps
1. Executed reproduction in Python REPL:
   ```python
   >>> isinstance(True, int)
   True
   >>> True > 0
   True
   >>> type(True) is int
   False
   ```
2. Realized that standard type-checking functions in Python libraries are unsafe for financial domain models unless booleans are explicitly excluded.

### Incorrect Assumptions Considered
- *Assumption:* "Just check `if type(value) != bool:` before checking `isinstance`."
  *Critique:* Fragile and verbose. Multiple type checks clutter the code.

### Final Technical Resolution
Implemented a dedicated, strict type guard `_is_valid_paise(value)` in `service.py`:
```python
def _is_valid_paise(value):
    """Accept positive integer paise, excluding bool."""
    return type(value) is int and value > 0
```
Using `type(value) is int` performs exact class equality, naturally rejecting subclasses including `bool`.

### Files and Functions Involved
- `service.py`: `_is_valid_paise()` and `apply_order_event()`

### Regression Test & Verification Result
- Verified by `test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]` and `test_invalid_refund_amounts_are_ignored[False]`.
- Result: **PASSED**. Both boolean values are safely rejected with 0 paise refunded.

### Remaining Limitations
- Upstream string numbers (e.g. `"500"`) are not automatically cast to `int`. Upstream callers must provide strongly-typed integers.

---

## 2. Challenge 2: Duplicate Event Replays Mutating Audit Trail

### Initial Symptoms
Running `test_acceptance_matrix.py::test_payment_event_replay_idempotent` failed across all 20 parametrized instances with:
```text
AssertionError: assert ['EV-000', 'EV-000'] == ['EV-000']
  Left contains one more item: 'EV-000'
```
Replaying an event did not change `payment_status`, but it appended duplicate event IDs into `processed_event_ids`.

### Root Cause
In the starter implementation of `apply_order_event`, the append operation `out["processed_event_ids"].append(event_id)` was executed at the bottom of the function without any prior membership check. Even though the state transition condition `if payment_status == "UNPAID"` prevented the status from changing again, the event ID was recorded a second time.

### Investigation Steps
1. Traced execution flow of `once = apply_order_event(order, event)` followed by `twice = apply_order_event(once, event)`.
2. Observed that `twice` entered the function, saw `payment_status == "PAID"`, skipped the state change, but fell through to line 132 where `append` executed unconditionally.

### Incorrect Assumptions Considered
- *Assumption:* "Use a `set` for `processed_event_ids` to naturally prevent duplicates."
  *Why Rejected:* The official data model in `models.py` defines `"processed_event_ids": []` as a list. JSON serialization fails on sets, and order-event contracts expect list types.

### Final Technical Resolution
Added an upfront idempotency guard immediately after event validation in `service.py`:
```python
# Prevent replaying an already processed event.
if event_id in processed_ids:
    return out
```
If an event ID has already been recorded, the function returns immediately without reaching any mutation or append logic.

### Files and Functions Involved
- `service.py`: `apply_order_event()` lines 56–58

### Regression Test & Verification Result
- Verified by all 20 cases of `test_payment_event_replay_idempotent` and `test_contract.py::test_duplicate_event_is_idempotent`.
- Result: **PASSED**.

### Remaining Limitations
- Lookup in a Python list is $O(K)$. For extremely long-lived entities with thousands of events, this could degrade performance without a secondary set index.

---

## 3. Challenge 3: Asymmetric Schema Field Names in Reconciliation

### Initial Symptoms
During reconciliation testing, `test_contract.py::test_reconcile_maps_internal_total_to_provider_amount` failed. Internal orders and provider records having identical amounts were erroneously reported under `amount_mismatches`.

### Root Cause
Internal orders created via `models.new_order` store transaction value in `total_paise`. Provider records from settlement gateways store transaction value in `amount_paise`. The original reconciliation code attempted direct equality comparison using a single hard-coded key `row.get("amount_paise")`, which evaluated to `None` on internal records.

### Investigation Steps
1. Compared dictionary structures between `fixtures.sample_orders()` and `fixtures.sample_provider_orders()`.
2. Verified that `total_paise` is the canonical internal attribute, while payment gateway webhooks use `amount_paise`.

### Final Technical Resolution
Implemented dynamic bidirectional fallback mapping in `service.reconcile_orders`:
```python
internal_amount = internal_record.get(
    "total_paise",
    internal_record.get("amount_paise")
)
provider_amount = provider_record.get(
    "amount_paise",
    provider_record.get("total_paise")
)
```
This ensures that whichever key is present on either record is extracted gracefully.

### Files and Functions Involved
- `service.py`: `reconcile_orders()` lines 186–195

### Regression Test & Verification Result
- Verified by `test_contract.py::test_reconcile_maps_internal_total_to_provider_amount`.
- Result: **PASSED**.

---

## 4. Challenge 4: Dual Mismatch Classification Independence

### Initial Symptoms
When an order had *both* an amount discrepancy and an operational status discrepancy (e.g. `ORD-1078` in `data/records.json` where internal amount=499, provider amount=500, internal status=`CANCELLED`, provider status=`DELIVERED`), the reconciliation logic placed it only in `amount_mismatches` or only in `status_mismatches`, depending on `if/elif` ordering.

### Root Cause
Using `if ... elif ... else` mutually exclusive blocks prevented an order from being flagged in both discrepancy categories simultaneously.

### Investigation Steps
1. Read `STUDENT_PROBLEM_STATEMENT.md` Requirement 6: "Report missing records, amount mismatches and status mismatches separately and deterministically."
2. Verified test `test_contract.py::test_reconcile_reports_amount_and_status_mismatch_together` expects the order ID to appear in **both** lists simultaneously.

### Final Technical Resolution
Decoupled the checks into independent condition blocks:
```python
if not amount_matches:
    report["amount_mismatches"].append(order_id)

if not status_matches:
    report["status_mismatches"].append(order_id)

if amount_matches and status_matches:
    report["matched"].append(order_id)
```

### Files and Functions Involved
- `service.py`: `reconcile_orders()` lines 210–217

### Regression Test & Verification Result
- Verified by `test_contract.py::test_reconcile_reports_amount_and_status_mismatch_together`.
- Result: **PASSED**.

---

## 5. Challenge 5: Out-of-Order Payment Confirmation Following Cancellation or Rejection

### Initial Symptoms
When an order was cancelled or rejected prior to payment confirmation (e.g. customer cancels an unpaid placed order, or kitchen rejects an unpaid placed order), `apply_order_event` transitioned the status to `CANCELLED` or `REJECTED`, leaving `payment_status = "UNPAID"` and `refund_due_paise = 0`. If a delayed webhook later delivered `payment_confirmed`, `payment_status` transitioned to `"PAID"`, but `refund_due_paise` remained 0. As a consequence, subsequent valid `refund_processed` events were rejected because `refund_due_paise` was zero.

### Root Cause
In `service.py`, `refund_due_paise` was only populated inside `restaurant_rejected` and `cancel_requested` branches if `payment_status == "PAID"`. The `payment_confirmed` branch updated `payment_status = "PAID"` without checking if the order was already in a terminal cancelled/rejected state requiring an immediate refund liability to be recorded.

### Investigation Steps
1. Traced asynchronous lifecycle where payment capture and kitchen response execute concurrently.
2. Verified that if money is captured on a cancelled or rejected order, that full amount represents an unfulfillable transaction that must immediately become refundable.
3. Observed that without setting `refund_due_paise = total_paise`, customer money was locked and unrefundable.

### Final Technical Resolution
In `service.py`, enhanced the `payment_confirmed` handler so that if the order is already in `REJECTED` or `CANCELLED` state, `refund_due_paise` is initialized to `total_paise`:
```python
if event_type == "payment_confirmed":
    if payment_status == "UNPAID":
        out["payment_status"] = "PAID"

        if status in ("REJECTED", "CANCELLED"):
            total = out.get("total_paise")
            if _is_valid_paise(total):
                out["refund_due_paise"] = total
```

### Files and Functions Involved
- `service.py`: `apply_order_event()`
- `tests/test_contract.py`: `test_rejection_then_payment_confirmed_then_refund` and `test_cancellation_then_payment_confirmed_then_refund`

### Regression Test & Verification Result
- Verified by:
  - `test_rejection_then_payment_confirmed_then_refund`
  - `test_cancellation_then_payment_confirmed_then_refund`
- Result: **PASSED**. Out-of-order payments correctly establish refund liability and allow full or partial refunds.

---

## 6. Summary of Challenges Classification

### Resolved Challenges
1. Python boolean subclass flaw in monetary integer validation.
2. Duplicate event replays mutating `processed_event_ids`.
3. Schema field name disparity (`total_paise` vs `amount_paise`) in ledger reconciliation.
4. Mutual exclusivity defect in dual mismatch reporting.
5. Ineligible order refund protection (enforcing `status in ("REJECTED", "CANCELLED")` and `payment_status == "PAID"`).

### Unresolved Challenges & Specification Ambiguities
1. **Cancellation After Dispatch:** The specification mandates that cancellation after dispatch must not silently change the order to `CANCELLED`. In the current implementation, it is handled as a silent no-op (returns unchanged state). The specification is silent on whether an error event or notification should be emitted.
2. **Missing `status` Key in Provider Records:**
   If a provider record completely lacks a `"status"` key, `service.py` evaluates the status comparison logic at lines 204–208:
   ```python
   status_matches = (
       "status" in internal_record
       and "status" in provider_record
       and internal_record["status"] == provider_record["status"]
   )
   ```
   Because `"status" in provider_record` evaluates to `False`, `status_matches` becomes `False`. Consequently, line 213 (`if not status_matches: report["status_mismatches"].append(order_id)`) appends the order to `status_mismatches`. The specification is silent on whether a missing schema key should trigger an error/malformed record bucket or be classified as a status mismatch, though treating absence of status as a status mismatch is a safe and defensive default.
3. **Duplicate `order_id` Entries in Reconciliation Summaries:**
   The specification states: *"Reconcile internal and provider summaries by order ID. Report missing records, amount mismatches and status mismatches separately and deterministically."*
   However, it does not define a separate output bucket for internal or provider batches that contain multiple differing records for the same `order_id`. `reconcile_orders()` handles this by pre-indexing records into a dictionary (`{row["order_id"]: row for row in ...}`), implementing Last-Write-Wins (LWW) semantics. This ensures deterministic $O(N+M)$ execution and complete crash resilience, though conflicting duplicates within a single side's summary are collapsed rather than flagged as internal data anomalies.
