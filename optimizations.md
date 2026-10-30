# Optimizations and trade-offs

This document records AI-assisted changes and design comparisons, as disclosed in [AI_USAGE.md](AI_USAGE.md). No performance benchmark was run and no speedup is claimed.

## 1. Baseline and objective

The immediate objective was correctness and maintainability. The untouched suite had **62 failures and 150 passes**. Unchecked refund arithmetic and replay handling made financial state unsafe; schema mismatch and absent status comparison made reconciliation inaccurate.

## 2. Options considered

- **Dictionary indexing versus nested scans:** retain indexing by order ID rather than compare every internal/provider pair. It keeps reconciliation straightforward and avoids quadratic lookup work.
- **Grouped fields versus last-row-wins:** preserve sets of normalized amounts/statuses for each ID. This uses additional memory for conflicting duplicates but makes reports independent of row order. Silently selecting the last record can hide a disagreement.
- **Persisted set versus existing event-ID list:** retain the public list format and its ordering. Replacing it with a set would change the returned data shape. An auxiliary set could accelerate lookup, but constructing it for each copied single-event call would still require scanning the history. No such cache was added.
- **Shallow versus deep copy:** preserve deep copying so returned history and nested metadata cannot mutate the caller's input. A shallow copy would save work but break this isolation guarantee.

## 3. Changes implemented

The lifecycle transition table centralizes allowed state changes. Shared identifier/paise validation keeps money and malformed-input rules consistent. Reconciliation normalizes fields once, groups them by ID, then sorts the ID union for deterministic output.

For `n` internal rows, `m` provider rows and `k` distinct usable IDs, indexing takes expected `O(n + m)` time and sorting takes `O(k log k)`. Memory is `O(n + m)` in the worst case when every normalized duplicate field differs. These are algorithmic bounds, not measured timings. Event application copies the order and scans its event history; with `h` stored IDs and otherwise bounded order metadata, that is `O(h)` time and memory per call.

Correctness is protected by all 301 passing tests, including duplicate/reversed reconciliation inputs, nested-copy isolation, replayed refunds and invalid amounts. The observed test runtime is verification evidence, not a performance comparison.

## 4. Trade-offs

The service favors explicit validation and stable reporting over coercing strings/floats into amounts or repairing inconsistent financial records. Duplicate summaries add some grouping complexity, but avoid silent overwrite. Keeping refused valid events in history costs storage while ensuring that replay after a state change remains harmless.

The function-based API remains small and dependency-free. It offers no transactional persistence or shared cache, so performance conclusions for a production service would be premature.

## 5. Further improvements

For a persistent service, store event IDs under a unique constraint and update financial balances in the same transaction. Validate this with concurrent duplicate delivery and crash/retry tests. For large reconciliation inputs, first measure row counts, duplicate rates, memory and elapsed time; then compare grouped in-memory indexing with a database or external-sort approach. Structured diagnostics for skipped malformed records would improve observability and should have tests proving reports and source inputs remain stable.
