# TESTING.md — OrderOps

## Environment and commands
- Windows, Python 3.11, PowerShell in VS Code.
- Baseline reported: `python -m pytest -q` → **150 passed, 62 failed, 1 warning**.
- Intermediate local run after replay guard: **171 passed, 41 failed, 1 warning**.
- Fix branch: `python -m pytest -q` → **212 passed, 1 warning in 0.84s**, subsequently **212 passed, 1 warning in 0.94s**.
- `python -m main` ran successfully.

## Five (plus) visible edge cases
The following behavior is covered by existing test cases included in the observed 212-pass run.

| # | Input / edge case | Expected | Observed evidence |
|---|---|---|---|
| 1 | Replay the same payment event ID | Processed once | `test_payment_event_replay_idempotent` |
| 2 | Refund amount -1 | Ignore refund | `test_invalid_refund_amounts_are_ignored` |
| 3 | Refund amount `True` | Ignore boolean amount | `test_invalid_refund_amounts_are_ignored` |
| 4 | Refund 1000 paise on an active, unpaid order | No refunded amount | `test_refund_eligibility_matrix` |
| 5 | Refund 4000, then 2000, against 5000 due | Reject second refund | `test_refunds_cannot_exceed_due` |
| 6 | Internal status PLACED, provider ACCEPTED, equal amount | Status mismatch, not matched | `test_reconciliation_status_mismatch_matrix` |
| 7 | Delivery attempt from PLACED | Status unchanged | `test_order_state_transition_matrix` |
| 8 | Full refund equals outstanding due | Mark payment REFUNDED | `test_valid_partial_and_full_refunds` |

## Demo output (observed)
```text
matched: []
missing_from_provider: ['ORD-103']
missing_from_internal: ['ORD-104']
amount_mismatches: ['ORD-101', 'ORD-102']
status_mismatches: ['ORD-102']
```

## Regression tests
The original visible test suites exercise many of these scenarios. Additional focused regression tests are introduced separately in `tests/test_regression_safety.py`; their execution result must be recorded after running pytest again.

## Remaining issues
- The latest observed fix-branch run had zero failed tests.
- One pytest deprecation warning originates from `anyio` using `CallSpec2`.
- The visible suite is not a guarantee of hidden-test completeness.
