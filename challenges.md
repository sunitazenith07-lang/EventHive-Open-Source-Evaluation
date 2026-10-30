# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour

The main confusing point was that the reconciliation example had equal monetary values for two shared orders, but the report still needed to distinguish a status mismatch. A second issue was the difference between the internal order's `total_paise` field and the provider summary's `amount_paise` field. The refund tests also exposed Python's special treatment of `bool` as a subclass of `int`.

## 2. Evidence

- The starter reconciliation code used an `if` for amount mismatch followed by an `else` that appended to `matched`; it never compared the two `status` values. The test `test_reconcile_reports_status_difference` expected order `A` in `status_mismatches` but received an empty list.
- Refund tests showed an invalid refund could be added directly. The pasted baseline output included `True` changing the total by 1, negative amounts reducing the total, oversized refunds exceeding the due, and `TypeError` for `None`, strings, lists, and dictionaries.
- During verification, the first revised demo run still showed amount mismatches for `ORD-101` and `ORD-102`. Inspecting the fixture records showed internal orders store the amount in `total_paise`, while provider summaries store it in `amount_paise`.

## 3. What I tried

1. Read the failing assertions and compared them with the relevant branches in `service.py`.
2. Replayed payment/refund events to understand why event IDs were duplicated and why the second refund could exceed the remaining amount.
3. Tried the acceptance-matrix refund inputs, including `True`, fractional values, missing values, strings, lists, and dictionaries; this showed why type validation must explicitly reject booleans and unsupported values before arithmetic.
4. Ran the offline demo after the initial reconciliation change. Its amount mismatch output led to checking the fixture field names rather than assuming both sources used the same key.
5. Ran the full suite and the demo again after mapping internal `total_paise` to provider `amount_paise`.

## 4. Resolution

Added event-ID validation and an early replay guard; unknown types and events without usable IDs are ignored. Refund processing now requires a paid rejected/cancelled order, positive integer paise, and an amount no greater than the outstanding due. Payment is marked `REFUNDED` only at exact completion. Reconciliation now validates both sides' amount and status fields independently, maps internal totals to provider amounts, and classifies a row as matched only when both values agree.

## 5. Proof and regression prevention

The final run passed **225 tests**. The supplied contract and acceptance-matrix tests passed unchanged. The new `tests/test_regressions.py` specifically covers duplicate refund replay, conflicting payload reuse, invalid refund types, refund bounds, exact full refund, simultaneous amount/status differences, missing summary fields, malformed events, wrong-order events, late payment, and `total_paise`/`amount_paise` mapping.

## 6. Unresolved challenge or next step

The implementation is an in-memory service, so processed event IDs are not retained across process restarts. Reconciliation also has no output category for duplicate records: when a side contains the same order ID more than once, the last row is used. A next iteration could introduce persistent idempotency storage and an explicit duplicate-record reporting policy, with tests for process restart and conflicting duplicate summaries.
