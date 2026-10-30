# Approach and implementation decisions

This is an AI-assisted engineering record. See [AI_USAGE.md](AI_USAGE.md) for the assistance disclosure; it is not an unaided-work declaration.

## 1. Baseline

The untouched starter was checked with Python 3.12.14 and pytest 9.2.0 in an isolated environment. Commands, from the repository root:

```sh
../orderops-venv/bin/python -m pip install -r requirements-dev.txt
../orderops-venv/bin/python -m pytest -q --tb=short
../orderops-venv/bin/python -m main
```

The baseline was **62 failed, 150 passed in 0.15s**. The demo reported `ORD-101` and `ORD-102` as amount mismatches, with no matches or status mismatches. The ordinary setup remains `python -m pip install -r requirements-dev.txt`; the relative interpreter above belongs to the local verification environment.

## 2. Codebase understanding

The PDF and student checklist were compared with the Markdown problem statement. Source, fixtures, dataset, tests, configuration, workflows and submission templates were inspected before editing.

`models.new_order()` creates an unpaid order with separate due/refunded balances and a list of processed IDs. `service.apply_order_event()` returns a copy after an event. `main.py` sends fixture summaries to `service.reconcile_orders()`. Internal fixtures and `data/records.json` store `total_paise`; provider summaries store `amount_paise`. Existing reconciliation tests instead use `amount_paise` on both sides, which left the demo schema defect uncovered.

## 3. Investigation and implementation strategy

- **Replay:** the starter appended every ID and applied effects before checking history. The existing duplicate-payment test showed repeated history entries. The fix validates the envelope, checks the ID before processing, and records each recognized, correctly addressed event once. Regression tests also replay a partial refund and reuse an ID with a conflicting payload.
- **Refund safety:** the starter added arbitrary amounts without checking eligibility or the outstanding balance. Baseline failures included negative, fractional, boolean, oversized and ineligible refunds; malformed amounts could raise type errors. Refund processing now requires a paid cancelled/rejected order, exact integer paise, and `0 < amount <= due - refunded`. Completion requires equality with the full due amount.
- **Reconciliation:** the starter compared only amounts and used the wrong internal field for fixture records. Amount normalization and separate amount/status comparisons fix both defects. Before implementation, the new reconciliation regressions produced **24 failed, 4 passed** against the starter. The full dataset independently established expected category counts of 107, 12, 25, 20 and 12 respectively for matched, missing provider, missing internal, amount mismatches and status mismatches.

## 4. Implementation decisions

A transition table keeps allowed lifecycle changes explicit. Dispatch still requires acceptance; cancellation after dispatch has no lifecycle effect. Payment confirmation changes `UNPAID` to `PAID`, establishes refund due when it arrives after cancellation/rejection, and cannot revive a fully refunded order.

Malformed envelopes leave the entire copied order unchanged. A recognized, addressed event with a valid ID is consumed even if its transition or refund is refused. This prevents a previously rejected event from acquiring a new effect on later replay. An omitted event `order_id` remains valid for the existing single-order API; an explicit target must match.

Reconciliation groups normalized fields by ID. Identical duplicate summaries collapse, while conflicting duplicates enter the relevant mismatch category. This avoids arbitrary last-row-wins behavior. Rows without usable IDs are skipped; identifiable invalid fields are mismatches. No new report categories or external dependencies were needed. A strict exception-based input API was considered, but retaining a usable report for mixed valid/malformed input fits this offline service better.

## 5. Verification

The original 212 tests remain unchanged. Two files add 89 cases: 61 event regressions and 28 reconciliation regressions. A complete local run after the fixes returned **301 passed in 0.07s**. The demo now matches `ORD-101`, reports the `ORD-102` status mismatch, and reports `ORD-103`/`ORD-104` missing from their respective sides, with no amount mismatches.

Tests cover replay and conflicting IDs, late/stale payments, partial and complete refunds, malformed input, wrong targets, nested-copy isolation, schema normalization, duplicate summaries, sorted reports and the supplied dataset. See [TESTING.md](TESTING.md) and [ORDER_FLOW_NOTES.md](ORDER_FLOW_NOTES.md). The service remains an in-memory, single-order function; it does not provide durable or concurrent payment processing.

Additional local probes processed 212 addressed dataset events, with seven unaddressed events skipped by the caller and no unknown target IDs. Replay stayed stable, inputs remained unchanged and balances stayed within `0 <= refunded <= due <= total`. A separate sweep of 784 malformed JSON field combinations found no exception or source mutation. Local verification used Python 3.12.14; Python 3.10/3.11 were unavailable locally, and the workflow targets Python 3.11. These local results do not claim a CI result.
