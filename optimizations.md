# optimizations.md - Required submission

Document optimizations you considered or implemented. Do not claim a speedup or improvement unless you measured it.

## 1. Baseline and objective
The objective was correctness, not speed. No performance optimization was made and no benchmark was run. The original suite had 62 failures in duplicate handling, refund validation, refund eligibility and reconciliation.

## 2. Options considered
- **Duplicate events:** chose a membership check on `processed_event_ids`. Rejected a `set` for faster lookup, because it would change the stored format and I did not measure any need. Risk: a missing or reused ID is treated as a duplicate.
- **Refund amounts:** chose inline validation. Rejected a helper function for now; four conditions are still readable. Risk: malformed refunds are ignored silently.
- **Refund eligibility:** chose payment status plus order status. Rejected payment status alone, since a paid order can still be delivered.
- **Reconciliation:** chose `if`/`elif`/`else` with a status check. Rejected independent amount and status checks, which would put one order in two lists. Risk: only the amount mismatch is reported when both differ.

## 3. Changes implemented
- Duplicate event check. Tests: `test_payment_event_replay_idempotent`, `test_refund_replay_same_event_id_not_applied_twice`.
- Refund amount and balance validation. Tests: `test_invalid_refund_amounts_are_ignored`, `test_refunds_cannot_exceed_due`.
- Refund eligibility check. Test: `test_refund_eligibility_matrix`.
- Reconciliation status comparison. Test: `test_reconciliation_status_mismatch_matrix`.
- Measurement: none. Correctness was verified with pytest; final suite 226 passed.

## 4. Trade-offs
- Inline conditions are simple but make the refund branch long.
- Strict validation protects data but hides malformed events.
- `if`/`elif` keeps one category per order but can hide a second mismatch.
- No refactoring, so the changes stay small and reviewable.

## 5. Further improvements
1. Decide whether reconciliation should report both mismatch types (failing test first).
2. Handle a missing `event_id` explicitly.
3. Log ignored refund events.
4. Benchmark reconciliation on a large synthetic dataset before any performance change.

If you made no optimization change, state that honestly and compare at least two reasonable options. Correctness and maintainability take priority over unnecessary complexity.