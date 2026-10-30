# optimizations.md - Required submission

## 1. Baseline and objective
Correctness needed improvement: duplicate refunds, invalid refund application, missed status mismatches, and false amount mismatches. Evidence came from 62 failing tests and the demo output.

## 2. Options considered
- Idempotency by event_id: prevents duplicate processing; risk is that invalid events consume their ID. Chosen because replay safety matters more than retrying with a changed payload.
- Strict refund validation: prevents negative, non-integer, over-limit, and ineligible refunds; risk is rejecting unusual but potentially valid inputs. Chosen because the contract requires integer paise and bounds.
- Independent reconciliation checks: reports amount and status mismatches separately; risk is a record appearing in both lists. Chosen because the edge-case catalog includes combined mismatches.
- Amount field fallback: supports both total_paise and amount_paise; risk is hiding a genuinely missing amount. Chosen because models and fixtures use total_paise internally.

## 3. Changes implemented
- Change: early idempotency guard in apply_order_event. Reason: prevent duplicate state changes. Tests: test_duplicate_event_is_idempotent and regression tests.
- Change: refund eligibility, type, sign, and cap validation. Reason: enforce refund safety. Tests: refund contract and acceptance-matrix tests.
- Change: payment-after-rejection handling. Reason: avoid paid eligible orders with zero refund due. Tests: regression test.
- Change: deterministic reconciliation with independent mismatch categories. Reason: detect status mismatches and combined mismatches. Tests: reconciliation contract and matrix tests.
- Change: defensive handling for missing/malformed inputs. Reason: avoid corrupting state. Tests: empty and malformed regression tests.

## 4. Trade-offs
Simplicity was prioritized over exhaustive validation: duplicate order IDs collapse to the first record, and anonymous events are not deduplicated. Correctness and deterministic output were prioritized over preserving every duplicate row.

## 5. Further improvements
With more time, I would add explicit duplicate-order reporting and event ordering checks, plus optional awaiting-refund CSV export. These would be validated with additional regression tests and the existing reconciliation suite.
