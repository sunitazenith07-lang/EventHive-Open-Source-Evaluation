# Technical challenges observed

> AI-assisted reference: this document records work performed by Codex, not an unaided student submission.

## Schema mismatch hidden behind a successful demo

There was no blocker preventing implementation. A notable investigation was why the
demo ran without exceptions yet showed no matched orders. `sample_orders()` returns
`total_paise`, while provider summaries contain `amount_paise`. The old comparison
looked up `amount_paise` on both sides, producing None internally. Normalizing the
two documented shapes fixes this without changing fixtures or hard-coding IDs.
`test_domain_totals_and_provider_amounts_reconcile_in_real_demo` verifies it.

## Rejected-event replay semantics

The brief defines replay safety but does not specify whether a premature refund
should become effective when replayed after later cancellation. This reference
records a recognized, addressed event ID even when no financial change is permitted.
The explicit regression
`test_rejected_refund_is_consumed_and_cannot_become_effective_on_replay` checks that
policy across payment and cancellation events. Malformed envelopes and unknown
order IDs remain exact no-ops instead.

## Conflicting summaries

The starter silently retained the last duplicate order ID. That makes results depend
on row order when duplicate summaries disagree. The reference rejects conflicts
with ValueError and collapses identical summaries. Regressions exercise both input
orders and both sides; another test checks all 36 permutations of a small report.

## Evidence and remaining limits

The baseline recorded 62 failures and 150 passes; the completed suite recorded
308 passes. The evidence directory contains the actual logs. The implementation
cannot prove payment-provider settlement or protect concurrent updates: it is a
pure, offline engine with no durable store. Semantically inconsistent historical
snapshots require a separately defined repair policy. No such migration was attempted.
