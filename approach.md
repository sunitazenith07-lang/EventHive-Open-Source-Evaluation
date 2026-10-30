# approach.md - OrderOps implementation record

AI assistance was used to investigate, edit, and test this change. Confirm the evaluation policy before using this as an evaluation submission; no no-AI declaration is made here.

## 1. Baseline
- Before editing: `python -m pip install -r requirements-dev.txt` succeeded; `python -m pytest -q` reported 62 failed, 150 passed in 2.91s.
- Baseline `python -m main`: status mismatches were empty although ORD-102 had differing internal/provider statuses.

## 2. Codebase understanding
- `service.py` owns event processing and order reconciliation; `models.py` creates standard order dictionaries.
- The tests exercise lifecycle transitions, replay handling, refund bounds/eligibility, malformed event types, and reconciliation reports.
- The offline demo compares fixtures by order ID.

## 3. Investigation and implementation
- Event replay: the baseline duplicate-payment test found duplicate IDs in `processed_event_ids`. Return unchanged state for already-seen IDs.
- Refund inputs: failures showed ineligible and invalid refunds could change totals. Require a paid cancelled/rejected order, positive integer paise, and amount within outstanding due.
- Reconciliation: status-difference tests failed because only amount was compared. Classify amount and status independently and match only when both agree.

## 4. Decisions
- Keep the existing branch-based handlers rather than add a dispatch registry for seven event types.
- Reject malformed or unknown event inputs without changing order state.
- Treat `REFUNDED` as complete only when `refunded_paise == refund_due_paise`.

## 5. Verification
- Added regressions for repeated refunds, malformed events, simultaneous reconciliation mismatches, and the complete paid-rejection refund flow.
- Focused tests: 218 passed; full final suite: 219 passed in 1.62s.
- Final demo reports ORD-102 in `status_mismatches`; `python -m main` exited successfully.
- Remaining limitation: duplicate summary rows sharing an order ID are collapsed by the existing dictionary construction; this behavior was not changed.