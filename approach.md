# Engineering approach

> AI-assisted implementation and notes. The student confirmed evaluator permission for AI assistance on 30 October 2026; Codex contributions are documented in AI_ASSISTANCE.md.

## Baseline and code flow

At upstream commit `e006d241e3d8ddf6520021a6ab554306a31a200b`, Codex installed
`requirements-dev.txt` in an isolated environment and ran `python -m pytest -q`
before editing. Actual result: **62 failed, 150 passed** (212 total).
The original demo ran successfully but misclassified ORD-101 and ORD-102 as amount
mismatches because it compared a missing internal `amount_paise` to provider values.

The inspected path was `models.new_order` -> fixtures ->
`service.apply_order_event` / `service.reconcile_orders` -> `main`. Both original
test files, the JSON dataset/schema, and GitHub Actions were inspected.

## Findings and implementation

The replay failures came from appending IDs without checking history. Refund
failures came from unconditional arithmetic without eligibility/type/balance guards.
Status mismatches came from an amount-only comparison. The demo exposed a second
reconciliation issue: internal and provider records use different amount keys.

The implementation preserves dictionaries and the two public function signatures.
A transition table expresses valid lifecycle moves. Event validation and a duplicate
check precede updates. Refunds update only after strict validation. Reconciliation
indexes normalized summaries, compares dimensions independently, and sorts the union
of IDs. Exact duplicates collapse; conflicting duplicates fail explicitly.

## Assumptions and alternatives

Known, addressed event IDs are consumed even for rejected transitions/refunds.
Malformed envelopes are not consumed. A payment arriving after cancellation/rejection
creates the full refund obligation. Fully refunded payments never return to PAID.
Malformed summary rows raise ValueError rather than being silently dropped.

A database, new framework, and production payment integration were outside the
exercise. A set-only event history was rejected to preserve the supplied serializable
list representation. No stretch feature was added.

## Verification

The final Desktop run on Python 3.14.7 produced **308 passed in 0.11s**,
including all 212 untouched original cases and 96 new regression cases.
`python -m main` produced the corrected report in `evidence/demo-output.txt`.
The larger dataset and a five-event refund walkthrough were executed and saved.
Existing tests, CI, models, fixtures, main, and synthetic data were not modified.
See TESTING.md for detailed evidence and GUIDE.md for the implementation plan.

Local tests do not establish remote CI or production results. The draft PR records
remote verification separately. These notes describe the AI-assisted
implementation work performed with evaluator permission confirmed by the student.
