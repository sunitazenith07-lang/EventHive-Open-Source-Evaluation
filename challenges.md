# Challenges and evidence

This record describes Codex's AI-assisted work, not independent student experience.

## Environment
The default Windows python command was an inaccessible application alias. The bundled Python
runtime worked but lacked pytest. Created an isolated virtual environment and installed the
repository development requirements successfully. Baseline then ran: 62 failed, 150 passed.

## Schema mismatch
The baseline demo called ORD-101 an amount mismatch although both sides represent 45900 paise.
Source inspection showed internal fixtures use total_paise and provider summaries use amount_paise.
Added fallback normalization without treating missing values as matching. The demo now matches ORD-101;
test_reconciliation_reports_both_differences_and_normalizes_total protects this behavior.

## Replay versus late notification
A replay guard alone does not protect against a new payment event ID after a full refund.
The payment handler previously unconditionally assigned PAID. The new handler preserves REFUNDED.
test_refund_sequence_and_replay verifies partial refund, exact replay, completion and late payment
in one sequence, including input immutability at each step.

## Duplicate reconciliation ambiguity
Silently choosing the last conflicting row makes output input-order dependent. Conflicting duplicate
IDs now raise ValueError in either input ordering; identical duplicates collapse.
This is covered by test_conflicting_duplicate_records_rejected_in_either_order.

## Remaining limitations
No major implementation blocker remains locally. The user connected GitHub and created a fork after local verification.
CI had not been observed when these notes were prepared. Persistence/concurrent processing would
require transactional event tracking; this offline pure-function exercise does not provide it.
