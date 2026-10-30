# OrderOps Testing Strategy & Evidence Log

> **Author:** Shubham Kumar
> **Repository:** `OrderOps-Open-Source-Evaluation`
> **Evaluation Component:** Mandatory Testing Documentation
> **Verification Command:** `python -m pytest -q`
> **Actual Summary:** `221 passed in 0.12s`

---

## Conflict & Pre-existing File Notice
This file replaces the starter prompt template `TESTING.md` (24 lines of instructional placeholders) with the completed engineering submission as required by `STUDENT_PROBLEM_STATEMENT.md`.

---

## 1. Test Command & Execution Environment

- **Operating System:** Windows 11 / Windows Server (win32)
- **Python Version:** Python 3.14.7 (requires-python: `>=3.10`)
- **Pytest Version:** `pytest-8.2.2`, `pluggy-1.7.0`, `iniconfig-2.3.1`, `packaging-26.3`
- **Configuration:** `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["."]`)
- **Exact Verification Command Run:**
  ```powershell
  python -m pytest -q
  ```
- **Actual Terminal Output:**
  ```text
  ................................................................................................................................................................................................................... [100%]
  221 passed in 0.12s
  ```

---

## 2. Test Suite Architecture & Contract Mapping

The automated test suite is organised into two distinct test modules under `tests/`:

| Test Module | Test Functions | Total Test Cases | Focus Area |
|---|---|---|---|
| `tests/test_contract.py` | 21 unique functions | 21 | Direct behavioral contract invariants, defensive programming, unhashable types, missing keys, field mapping. |
| `tests/test_acceptance_matrix.py` | 14 unique functions | 200 | Parametrized combinatorial matrix testing: state transitions (26), event idempotency (20), valid refund ranges (10), invalid refund types (15), refund eligibility combinations (12), cumulative refund arithmetic (20), reconciliation status/amount variations (32), determinism (10), and rejection total scales (10). |

---

## 3. Five Detailed Edge Cases (Evidence-Based)

The following 5 edge cases represent critical distributed systems failure modes verified against the implementation:

| # | Edge Case / Input Scenario | Expected Behaviour | Actual Observed Result | Verifying Test Name |
|---|---|---|---|---|
| 1 | **Customer requests cancellation after rider dispatch**<br>`order = {"status": "OUT_FOR_DELIVERY"}`<br>`event = {"type": "cancel_requested"}` | Status must **not** change to `CANCELLED`. State remains `OUT_FOR_DELIVERY`. | Order status remains `"OUT_FOR_DELIVERY"`. | `test_contract.py::test_cancel_after_dispatch_is_ignored` |
| 2 | **Duplicate refund event replay with identical ID**<br>`order = {"status": "CANCELLED", "payment_status": "PAID", "refund_due_paise": 5000}`<br>`event = {"event_id": "EV-001", "type": "payment_confirmed"}` sent twice | Replaying an event must not change state or append duplicate ID to audit log. | `twice["processed_event_ids"] == ["EV-001"]`. | `test_acceptance_matrix.py::test_payment_event_replay_idempotent[EV-001]` |
| 3 | **Boolean `True` passed as refund amount**<br>`event = {"type": "refund_processed", "amount_paise": True}` | Booleans must be strictly rejected as invalid paise amounts without incrementing refund totals. | `result["refunded_paise"] == 0`, `payment_status == "PAID"`. | `test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True]` |
| 4 | **Cumulative partial refunds exceeding refundable due balance**<br>`order.refund_due_paise = 5000`<br>Event 1: 4000 paise<br>Event 2: 2000 paise | First refund accepted (`refunded_paise = 4000`). Second refund exceeds remaining 1000 due; rejected completely. | After 2nd event: `refunded_paise == 4000` (does not become 6000). | `test_acceptance_matrix.py::test_refunds_cannot_exceed_due[4000-2000]` |
| 5 | **Simultaneous amount and status discrepancy in reconciliation**<br>Internal: `total_paise: 100, status: "ACCEPTED"`<br>Provider: `amount_paise: 90, status: "CANCELLED"` | Order ID must be reported in **both** `amount_mismatches` and `status_mismatches`, and excluded from `matched`. | `report["amount_mismatches"] == ["A"]`<br>`report["status_mismatches"] == ["A"]`<br>`report["matched"] == []` | `test_contract.py::test_reconcile_reports_amount_and_status_mismatch_together` |

---

## 4. Test Categories: Positive, Negative & Boundary

### Positive Test Cases
- Order progression through the happy path: `PLACED -> ACCEPTED -> OUT_FOR_DELIVERY -> DELIVERED` (`test_delivery_state_flow`).
- `payment_confirmed` advancing `payment_status` from `UNPAID -> PAID`.
- `restaurant_rejected` on a paid order correctly populating `refund_due_paise = total_paise` across 10 scales (1 to 99,999 paise).
- Partial refunds correctly incrementing `refunded_paise` while keeping `payment_status = "PAID"`.
- Full refund matching `refund_due_paise` automatically advancing `payment_status -> "REFUNDED"`.

### Negative Test Cases
- Unknown event types (`"unexpected_event"`, `"chargeback"`, `""`, `None`, `123`) discarded without mutation.
- Non-dictionary event payloads (`None`, `[]`, `"string"`, `123`) ignored safely.
- Unhashable event types (lists, dictionaries) safely discarded without raising `TypeError`.
- Missing `event_id` or blank `event_id` strings (`"   "`) rejected without modifying processed IDs.
- Ineligible order states (`PLACED`, `ACCEPTED`, `DELIVERED`, `OUT_FOR_DELIVERY`) attempting refund discarded with 0 refunded paise.

### Boundary Test Cases
- Refund amount exactly 1 paisa (minimum valid unit).
- Refund amount exactly matching outstanding balance ($outstanding = due - refunded$).
- Refund amount exceeding outstanding balance by exactly 1 paisa (e.g. 2501 on 2500 outstanding) rejected.
- Zero refund (`amount_paise = 0`) rejected.
- Negative refund (`amount_paise = -1`) rejected.
- Float refund (`amount_paise = 0.5`, `2.2`) rejected.

---

## 5. Synthetic Dataset Validation Coverage

The test suite's coverage was mapped directly against the 219 synthetic events and 12 documented reconciliation edge cases in `data/records.json`:

| Documented Dataset Anomaly | Occurrences in Dataset | Handled by Implementation? | Covered by Automated Test Suite? |
|---|---|---|---|
| Missing `event_id` | 7 events | Yes (discarded) | Yes (`test_missing_event_id_is_ignored`) |
| Missing `order_id` / Malformed payload | 7 events | Yes (discarded) | Yes (`test_non_dictionary_event_is_ignored`) |
| Unknown event type (`unexpected_event`) | 10 events | Yes (discarded) | Yes (`test_unknown_event_does_not_mutate_order_state`) |
| Duplicate identical `event_id` | 11 duplicate groups | Yes (idempotent) | Yes (`test_payment_event_replay_idempotent`) |
| Invalid refund amount types (null, bool, float, str, neg) | 17 events | Yes (rejected) | Yes (`test_invalid_refund_amounts_are_ignored`) |
| Cumulative refund exceeding due | Documented in catalog | Yes (rejected) | Yes (`test_refunds_cannot_exceed_due`) |
| Cancellation after dispatch | Documented in catalog | Yes (blocked) | Yes (`test_cancel_after_dispatch_is_ignored`) |
| Provider-only records | 25 records | Yes (reported) | Yes (`test_provider_only_order_is_reported`) |
| Internal-only records | 12 records | Yes (reported) | Yes (`test_internal_only_order_is_reported`) |
| Dual amount + status discrepancy | 1 record (`ORD-1078`) | Yes (reported in both) | Yes (`test_reconcile_reports_amount_and_status_mismatch_together`) |

---

## 6. Known Test Limitations

1. **In-Memory Fixtures vs Disk Ingestion:**
   The pytest suite tests the domain logic via programmatic in-memory dictionaries (`models.new_order()`) rather than loading `data/records.json` from disk. A full integration test reading `data/records.json` directly would further protect against file parsing regressions.
2. **Missing `dispatch_started` Rejection Matrix Row:**
   `test_order_state_transition_matrix` tests dispatch from `PLACED`, `ACCEPTED`, `OUT_FOR_DELIVERY`, and `DELIVERED`, but does not explicitly assert dispatch from `REJECTED` or `CANCELLED`. The code correctly enforces `status == "ACCEPTED"`, but a matrix row would document this explicitly.
3. **Refund-Specific Idempotency Test:**
   `test_payment_event_replay_idempotent` covers idempotency via `payment_confirmed` across 20 IDs. An explicit test replaying `refund_processed` with the same `event_id` is covered by the generic idempotency check, but having a dedicated test asserting `refunded_paise` does not double on replay provides additional regression confidence.
