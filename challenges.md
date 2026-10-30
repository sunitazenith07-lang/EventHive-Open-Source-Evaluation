# Challenges and debugging

This record describes work performed with Codex assistance; see [AI_USAGE.md](AI_USAGE.md). No major implementation blocker required a workaround. The most demanding cases were replay after a refusal and reconciliation across different input schemas.

## 1. Challenge or confusing behaviour

A rejected transition is harmless initially but can become valid later. For example, dispatch on a placed order must be refused. If that event is replayed after restaurant acceptance, processing it for the first time would violate the requirement that replay cannot produce a second effect.

A separate misleading result came from the demo: a genuinely equal order total was reported as an amount mismatch, while the existing amount-comparison tests exercised a different internal schema.

## 2. Evidence

The untouched suite returned **62 failed, 150 passed**. Its duplicate-payment assertion observed `['e1', 'e1']` instead of `['e1']`. The baseline demo reported both `ORD-101` and `ORD-102` as amount mismatches and no status mismatches.

Inspection showed that internal fixtures use `total_paise`, whereas the starter compared `amount_paise` on both sides. Status was never compared. The dataset catalog also includes conflicting repeated event IDs, partial refunds, malformed records and simultaneous amount/status differences.

## 3. What was tried

The investigation compared the demo records with the test inputs and read the event/data edge-case catalog. New reconciliation tests were run against the starter: **24 failed, 4 passed**. This reproduced the schema issue and exposed missing validation, independent mismatch reporting and duplicate-summary handling.

Event regressions then exercised early dispatch followed by acceptance and replay, and an ineligible refund followed by cancellation and replay. Related cases checked conflicting payloads sharing an ID and a fresh payment notification after full refund. These tests verify behavior across a sequence, rather than only checking one isolated event.

## 4. Resolution

Envelope validation and the processed-ID check now precede state changes. Recognized, correctly addressed events are recorded even when refused; malformed envelopes are ignored without history changes. Thus the original refusal remains stable on replay.

Reconciliation normalizes internal amounts, compares amounts and statuses independently, and requires both valid fields to match. Grouped field sets preserve conflicting duplicates instead of overwriting them. Missing fields on both sides cannot accidentally count as agreement.

Refund accounting validates the existing balances before applying any event and accepts only positive exact-integer refunds within the outstanding amount. Payment confirmation is monotonic and handles unpaid cancellation/rejection followed by late payment.

## 5. Proof and regression prevention

`test_rejected_transition_is_recorded_and_cannot_apply_on_later_replay` and `test_ineligible_refund_cannot_be_replayed_after_cancellation` protect the replay decision. `test_demo_reconciles_internal_totals_and_provider_amounts` protects the schema correction. `test_dataset_reconciliation_preserves_both_mismatch_categories` verifies the dataset counts, sorted output, reverse-input stability and the order that has both mismatches.

The event regression file passed all 61 cases. The complete suite after the implementation passed all **301 cases**. No original tests or CI checks were weakened.

An additional dataset-stream probe checked 212 addressed events for stable replay, unchanged source objects and bounded balances; the caller skipped seven events without targets. A separate malformed-field sweep covered 784 combinations without exceptions or source mutation.

## 6. Unresolved challenge or next step

The API has no persistent event store, transaction boundary or concurrency control. A real multi-worker service would need an atomic event-ID uniqueness constraint together with the balance update. That should be investigated with simultaneous-event and restart tests before connecting to payment infrastructure.

Input handling is intentionally conservative: events on invalid accounting snapshots are ignored; reconciliation skips unidentifiable rows and reports malformed identifiable fields as mismatches. There is no separate diagnostic channel for skipped rows or refused events. Adding structured diagnostics would make future investigations easier without silently repairing historical snapshots.
