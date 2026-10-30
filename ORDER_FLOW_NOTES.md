# OrderOps Order Flow Notes & Lifecycle Traces

> **Author:** Shubham Kumar
> **Repository:** `OrderOps-Open-Source-Evaluation`
> **Evaluation Component:** Mandatory Submission (`ORDER_FLOW_NOTES.md`)
> **Document Purpose:** Concrete, step-by-step order lifecycle traces, edge-case analysis, and architectural assumptions.

---

## Conflict & Pre-existing File Notice
This file replaces the starter prompt template `ORDER_FLOW_NOTES.md` (22 lines of instructional placeholders) with the completed engineering submission as required by `STUDENT_PROBLEM_STATEMENT.md`.

---

## 1. Complete Representative Event Sequence

The table below traces a real-world asynchronous food-ordering journey for Order `ORD-2001` with an initial total value of ₹450.00 (`total_paise: 45000`).

### Scenario Narrative
1. Customer initiates an order (`total_paise = 45000`).
2. Payment gateway confirms successful card authorization (`payment_confirmed`).
3. Restaurant kitchen accepts the order (`restaurant_accepted`).
4. Kitchen experiences equipment failure / stockout and sends a late cancellation request (`cancel_requested`).
5. Banking partner issues a partial refund installment of ₹200.00 (`refund_processed: 20000`).
6. Banking partner completes the remaining refund of ₹250.00 (`refund_processed: 25000`).
7. Banking partner mistakenly replays the final refund notification (`refund_processed: 25000` with duplicate `event_id`).

### Step-by-Step Lifecycle Execution Table

| Step | Event Name | State Before | Event Payload | Preconditions Evaluated | Expected State After | Payment Status | Refund Due (paise) | Refunded (paise) | Processed Event IDs | Actual Implementation Result |
|---|---|---|---|---|---|---|---|---|---|---|
| **0** | *(Creation)* | — | `new_order("ORD-2001", 45000)` | Initial constructor | `PLACED` | `UNPAID` | 0 | 0 | `[]` | Matches expected |
| **1** | `payment_confirmed` | `PLACED` | `{"event_id": "EV-101", "type": "payment_confirmed"}` | `payment_status == "UNPAID"` | `PLACED` | `PAID` | 0 | 0 | `["EV-101"]` | Matches expected |
| **2** | `restaurant_accepted` | `PLACED` | `{"event_id": "EV-102", "type": "restaurant_accepted"}` | `status == "PLACED"` | `ACCEPTED` | `PAID` | 0 | 0 | `["EV-101", "EV-102"]` | Matches expected |
| **3** | `cancel_requested` | `ACCEPTED` | `{"event_id": "EV-103", "type": "cancel_requested"}` | `status in ("PLACED", "ACCEPTED")`, `payment_status == "PAID"` | `CANCELLED` | `PAID` | 45000 | 0 | `["EV-101", "EV-102", "EV-103"]` | Matches expected |
| **4** | `refund_processed` (Partial) | `CANCELLED` | `{"event_id": "EV-104", "type": "refund_processed", "amount_paise": 20000}` | `status in ("REJECTED", "CANCELLED")`, `payment_status == "PAID"`, `20000 <= 45000` | `CANCELLED` | `PAID` *(Partial)* | 45000 | 20000 | `["EV-101", "EV-102", "EV-103", "EV-104"]` | Matches expected |
| **5** | `refund_processed` (Full) | `CANCELLED` | `{"event_id": "EV-105", "type": "refund_processed", "amount_paise": 25000}` | Outstanding: $45000 - 20000 = 25000$. Amount $25000 == 25000$. Full refund reached. | `CANCELLED` | `REFUNDED` | 45000 | 45000 | `["EV-101", ..., "EV-105"]` | Matches expected |
| **6** | `refund_processed` (Duplicate Replay) | `CANCELLED` | `{"event_id": "EV-105", "type": "refund_processed", "amount_paise": 25000}` | `event_id in processed_event_ids` -> Idempotent guard triggers early exit | `CANCELLED` | `REFUNDED` | 45000 | 45000 | `["EV-101", ..., "EV-105"]` | Duplicate discarded cleanly; no double refund |

---

## 2. Three Detailed Edge Cases

### Edge Case 1: Post-Dispatch Cancellation Attempt
- **Initial State:**
  `order = {"order_id": "ORD-3001", "total_paise": 1000, "status": "OUT_FOR_DELIVERY", "payment_status": "PAID", "refund_due_paise": 0, "refunded_paise": 0, "processed_event_ids": ["EV-01", "EV-02", "EV-03"]}`
- **Event Applied:**
  `{"event_id": "EV-04", "type": "cancel_requested"}`
- **Precondition Evaluation:**
  `service.py` evaluates: `if status in ("PLACED", "ACCEPTED"):`. Since `status == "OUT_FOR_DELIVERY"`, condition is `False`.
- **Expected Behaviour:**
  The cancellation request must be completely rejected. The order must remain `OUT_FOR_DELIVERY`, `refund_due_paise` must remain 0, and the event ID is appended to `processed_event_ids` to mark the attempt as evaluated.
- **Actual Observed Result:**
  Order status remains `"OUT_FOR_DELIVERY"`. No financial fields are mutated.
- **Verifying Test:** `tests/test_contract.py::test_cancel_after_dispatch_is_ignored`.

---

### Edge Case 2: Out-of-Order Payment Confirmation Following Rejection
- **Initial State:**
  Order `ORD-3002` created with `total_paise: 2500`. Restaurant rejects order before payment gateway confirmation arrives:
  - Step 1: `restaurant_rejected` arrives while order is `payment_status == "UNPAID"`.
    Order transitions `PLACED -> REJECTED`. Because `payment_status != "PAID"`, `refund_due_paise` remains 0.
  - Step 2: `payment_confirmed` arrives late.
- **Event Applied:**
  `{"event_id": "EV-02", "type": "payment_confirmed"}`
- **Precondition Evaluation:**
  `if payment_status == "UNPAID": out["payment_status"] = "PAID"`.
- **Expected Behaviour:**
  Payment status advances to `PAID`. Order remains `REJECTED`. Crucially, because funds have now been captured for an unfulfillable rejected order, `refund_due_paise` must immediately be initialized to `total_paise` (2500), enabling refund processing.
- **Implementation Behaviour & Resolution:**
  In `service.py`, `apply_order_event()` inspects whether the current status is `REJECTED` or `CANCELLED` upon receiving `payment_confirmed`. If so, it verifies that `total_paise` is valid and sets `refund_due_paise = total_paise`.
- **Actual Observed Result:**
  `result["status"] == "REJECTED"`, `result["payment_status"] == "PAID"`, `result["refund_due_paise"] == 2500`. Subsequent `refund_processed` events successfully issue partial or full refunds.
- **Verifying Test:** `tests/test_contract.py::test_rejection_then_payment_confirmed_then_refund`.

---

### Edge Case 3: Over-Refund Attempt Exceeding Outstanding Balance by ₹0.01
- **Initial State:**
  `order = {"order_id": "ORD-3003", "total_paise": 5000, "status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 5000, "refunded_paise": 4000, "processed_event_ids": ["EV-01", "EV-02"]}`
  Remaining outstanding refundable balance = ₹10.00 (`1000` paise).
- **Event Applied:**
  `{"event_id": "EV-03", "type": "refund_processed", "amount_paise": 1001}` (₹10.01 requested)
- **Precondition Evaluation:**
  `outstanding = due - refunded` ($5000 - 4000 = 1000$).
  `if outstanding <= 0 or amount > outstanding:` ($1001 > 1000$ evaluates to `True`).
- **Expected Behaviour:**
  The refund event must be rejected in its entirety. `refunded_paise` must remain 4000 (no partial 1000-paise absorption), and `payment_status` must remain `"PAID"`.
- **Actual Observed Result:**
  `result["refunded_paise"] == 4000`, `result["payment_status"] == "PAID"`.
- **Verifying Test:** `tests/test_acceptance_matrix.py::test_refunds_cannot_exceed_due`.

---

## 3. Assumptions and Architectural Limitations

1. **Cancellation Eligibility Window:**
   Customer cancellation is strictly accepted only while the order is in `PLACED` or `ACCEPTED` status. Once dispatched (`OUT_FOR_DELIVERY`), physical transit has begun and algorithmic cancellation is forbidden.
2. **Terminal Delivery State:**
   Orders in `DELIVERED`, `CANCELLED`, or `REJECTED` are treated as terminal operational states.
3. **Refund Currency Standard:**
   All monetary amounts are strictly positive integer paise (₹1 = 100 paise). Any non-integer type (including `bool`, `float`, and `str`) is treated as malformed and dropped.
4. **Independent Partial Refunds:**
   Multiple partial refunds are supported as long as the cumulative total does not exceed `refund_due_paise`. The `payment_status` transitions to `"REFUNDED"` if and only if `refunded_paise == refund_due_paise`.
5. **Reconciliation Summary Deduplication (Last-Write-Wins):**
   `reconcile_orders()` expects pre-aggregated summary lists where `order_id` is unique (the evaluation dataset contains 0 duplicate order IDs in `orders` and `provider_records`). If duplicate `order_id` rows appear within `internal` or `provider`, hash-map indexing resolves collisions via **Last-Write-Wins (LWW)**, where later entries supersede earlier ones. In production systems, an upstream aggregation or duplicate-flagging step should precede point-in-time reconciliation.
