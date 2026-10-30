# optimizations.md

## 1. Baseline and objective
The priority was **correctness and maintainability**, not speed. The starter was fast but wrong: 62 failing tests, and it accepted double, negative and ineligible refunds.

The starter also had a maintainability problem. Its transition rules were spread across an `if/elif` chain, and invalid events fell through silently. That made it hard to see why an event did nothing.

The data is small: 150 orders, 219 events, 163 provider rows. A per-event `deepcopy` and a list lookup for event ids are not a practical bottleneck.

## 2. Options considered
| Option | Expected benefit | Risk / reason | Decision |
|---|---|---|---|
| One `TRANSITIONS` table for status changes | One place to read and change the state machine; fewer branches to test | None significant | **Implemented** |
| Return an outcome reason from `evaluate_order_event` | Every no-op is explainable; tests can assert *why* | Extra function; kept `apply_order_event` signature unchanged | **Implemented** |
| Store `processed_event_ids` as a `set` | O(1) duplicate check instead of O(n) | Tests compare it to a list (`== ["e1"]`); a set is not JSON-serialisable and loses order. Per-order lists stay a handful of items long | Rejected |
| Avoid `deepcopy` per event in `process_events` (copy each order once, then mutate) | Fewer copies when one order gets many events | Loses the "input never mutated" guarantee at function level, which a test protects; measured cost already ~1 ms per full dataset run | Rejected for now |
| Cap over-limit refunds at the outstanding amount | "More helpful" — something gets applied | Hides a real provider/internal disagreement from reconciliation; a test requires rejection | Rejected |
| Record rejected event ids too | Strict whole-stream replay equality | Permanently loses an early, legitimate refund notification (see challenges.md) | Rejected |
| Index reconciliation rows once in a dict | O(n) instead of nested search | Already how the starter did it; kept | Kept |

## 3. Changes implemented
- **Change:** state-transition table plus explicit outcome codes (`applied`, `duplicate_event`, `invalid_transition`, `invalid_refund_amount`, `refund_not_eligible`, `refund_exceeds_outstanding`, …).
  - **Reason:** the rules can be read in one place, and `process_events` can return a rejection list.
  - **Tests:** the 26-case transition matrix plus `test_cancel_after_dispatch_reports_invalid_transition`.
- **Change:** reconciliation checks amount, status and payment status independently, in a single sorted pass.
  - **Reason:** the starter's `elif` hid a status mismatch behind an amount mismatch.
  - **Tests:** `test_amount_and_status_mismatch_are_both_reported` and `test_reconciliation_report_is_independent_of_input_order`.
- **Measurement method:** `time.perf_counter()` over 200 repetitions on `data/records.json`, Python 3.13.18, in this environment.
  - `process_events` (150 orders, 219 events): **~1.19 ms per run**
  - `reconcile_orders` (150 vs 163 rows): **~0.09 ms per run**

  These are absolute timings of the fixed code. The starter was not timed against it, because a speed comparison with an incorrect implementation is not meaningful.

## 4. Trade-offs
- Correctness was preferred over the cheapest code path. Each event still deep-copies the order, so `apply_order_event` stays pure and safe to call on shared data.
- Adding `payment_status_mismatches` and `invalid_records` to the report makes it slightly larger. In return, malformed rows and refund-state disagreements are no longer silently dropped. Existing tests that check `matched`, the mismatch lists and the empty report still pass unchanged.

## 5. Further improvements
- **Out-of-order queue:** park events that are rejected only because they are early (e.g. a refund before the rejection), and retry them after the next successful transition. Validate with the ORD-1007 trace expecting the refund on the first pass.
- **Global event-id registry** in `process_events`, to detect one id reused across orders.
- **Copy each order once per batch** in `process_events` if event volumes grow. Validate with a benchmark on a synthetic 100k-event stream and the existing mutation tests.
