# optimizations.md

## 1. Baseline and objective
- What needed improvement: correctness first (duplicate events, unsafe refunds, missing status comparison), then maintainability. Performance was never a problem: the whole suite runs in well under a second.
- Evidence: 62 failing tests on the starter, and the `if/elif` chain in `apply_order_event` mixing validation, state changes and bookkeeping in one block.

## 2. Options considered
| Option | Expected benefit | Risk / reason |
|---|---|---|
| Move refund and id validation into small helpers | Each rule has one named place and is easy to explain | Slightly more functions. **Implemented.** |
| Index reconciliation rows once into dicts keyed by `order_id` | One lookup per id instead of scanning lists; the starter already did this | None. **Kept and extended** to skip unusable rows. |
| Replace the `processed_event_ids` list scan with a set | O(1) instead of O(n) duplicate check | The order dict and the tests use a list (`processed_event_ids == ["e1"]`), so a set would need a second structure kept in sync. **Rejected**, not worth the complexity at this size. |
| Table-driven state transitions instead of `if/elif` | Easier to read and extend | Bigger diff than the bugs needed, and refund-due side effects do not fit a plain table. **Rejected for now.** |
| Record an event id only when the event was applied | Late refund notifications can be retried | Needs a restructure of the transition chain and a clear rule for replays of ignored events. **Rejected for now**, listed as a next step. |
| Trim an over-limit refund to the outstanding amount | Fewer rejected refunds | The tests require an over-limit refund to be ignored. **Rejected.** |

## 3. Changes implemented
- Change: helper functions (`_is_valid_id`, `_is_valid_amount`, `_mark_refund_due`, `_apply_refund`, `_index_by_order_id`, `_amount`) and a shared `REFUNDABLE_STATUSES` constant.
- Reason: the refund rule appears in the eligibility check, the late-payment path and the completion check, so naming it once avoids drift between them.
- Tests used to protect correctness: the original 212 tests plus the 34 cases in `tests/test_regressions.py`; all 246 pass.
- Measurement: none. I did not measure speed or memory, so I make no performance claim.

## 4. Trade-offs
- Simplicity vs late-event handling: recording every event with a usable id is simple and predictable, but a refund notification that arrives too early is lost.
- Strictness vs tolerance: refund amounts must be real integers, so `1000.0` is rejected even though it is numerically valid. This follows "integer paise" but may be stricter than a real provider feed.
- Silent skipping vs reporting: reconciliation skips rows with no usable `order_id` rather than adding a new report key that existing callers might not expect.

## 5. Further improvements
- Keep unapplied refund notifications as pending and re-apply them when the order becomes cancelled or rejected. Validate with a test that sends the refund first.
- Report skipped and duplicate reconciliation rows in a separate, clearly named key. Validate by adding tests that expect it and checking the demo output.
- Only if event histories grow large: keep a set alongside the list for duplicate checks, and measure with `timeit` on thousands of events before and after.