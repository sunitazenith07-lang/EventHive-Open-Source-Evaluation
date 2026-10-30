# approach.md - Required submission

## 1. Baseline

- Commands run before editing: `py -m pip install -r requirements-dev.txt`, `py -m pytest -q`, and `py -m main` from the project directory.
- Initial test result: Python 3.14.7 on Windows; **150 passed, 62 failed (212 total)** in 1.56 seconds.
- Demo/output observed on the starter: the report identified `ORD-103` as missing from the provider and `ORD-104` as missing internally. It listed amount mismatches for `ORD-101` and `ORD-102`, while failing to report the status difference for `ORD-102` (`ACCEPTED` internally versus `CANCELLED` at the provider).

## 2. Codebase understanding

- Important files and functions inspected: `service.py` (`apply_order_event`, `reconcile_orders`), `models.py` (`new_order`), `fixtures.py`, `main.py`, both supplied tests, `data/README.txt`, `data/records.json`, `requirements-dev.txt`, `pyproject.toml`, `.gitignore`, and both `.github/workflows/` files.
- Order lifecycle/data flow traced: `new_order` creates a `PLACED`/`UNPAID` record. `apply_order_event` returns an updated copy as payment, restaurant, dispatch, delivery, cancellation, and refund events arrive. The demo obtains internal/provider summaries from `fixtures.py`, passes them to `reconcile_orders`, and prints each report bucket.
- How understanding was confirmed: read the assertions in the contract and acceptance-matrix tests, ran the initial test suite and demo, inspected the synthetic dataset schema and edge-case catalog, then ran the updated tests and demo after the changes. I also ran reconciliation over the full synthetic dataset (150 internal orders and 163 provider records), which returned 107 matched, 12 missing from provider, 25 missing from internal, 20 amount mismatches, and 12 status mismatches.

## 3. Investigation and implementation strategy

- **Issue 1 — duplicate event replay:** the starter always appended `event_id` and never checked the processed-ID ledger. The contract replay test showed `['e1', 'e1']` instead of `['e1']`; the acceptance matrix repeated the same failure for 20 IDs. Added an early duplicate check and record recognized event IDs once.
- **Issue 2 — unsafe refunds:** the starter added `amount_paise` without checking payment eligibility, order status, integer type, positivity, or outstanding balance. Failures included negative and fractional amounts changing the total, `True` being treated as 1, over-refunds being accepted, and `None`/strings/containers raising `TypeError`. Added strict integer-paise validation (excluding `bool`), eligibility checks, and a bound against the outstanding due. Full completion now requires equality with the due amount.
- **Issue 3 — reconciliation status and field mapping:** the starter placed an order in `matched` whenever amounts were equal, without checking status. The status-matrix tests showed all differing statuses misclassified. The sample data also uses `total_paise` on internal orders and `amount_paise` on provider summaries. Updated reconciliation to compare those corresponding fields, to report amount and status differences independently, and to add an order to `matched` only when neither differs.
- Additional malformed-input handling: missing/blank event IDs, unknown or non-string event types, wrong-order event IDs, malformed reconciliation rows, missing summary fields, and non-integer amount values are handled without raising or mutating the input order.

## 4. Implementation decisions

- Main changes and why: small validation helpers keep the rules explicit; `deepcopy` remains in place so changes to the nested `processed_event_ids` list do not mutate the caller's order; a recognized event ID is consumed once even when that event is invalid for the current state, preventing a different payload from reusing it; reconciliation uses indexed records and sorted report lists.
- Alternatives considered and why rejected: a shallow copy was rejected because the processed-ID list is mutable and could leak changes to the input. Silently clipping an oversized refund to the remaining balance was rejected; the event is rejected as a whole, consistent with the tests' expected behavior. Treating an equal amount as a match without checking status was rejected because it hides a reconciliation discrepancy.
- Assumptions: event IDs are non-empty strings or integers; an event with an explicit `order_id` must target the supplied order; only listed event types are recognized; each side should normally contain one authoritative record per order ID.

## 5. Verification

- Tests added: 13 regression tests in `tests/test_regressions.py`. The two supplied test files were preserved unchanged.
- Commands run and actual results: `python -m pytest -q` under Python 3.13.5 — **225 passed, 0 failed** in 0.16 seconds; `python -m compileall -q .` — success; `python -m main` — success with `ORD-101` matched, `ORD-103` missing from provider, `ORD-104` missing internally, and `ORD-102` in status mismatches.
- Edge cases verified: repeated refund ID, conflicting payload under a reused ID, malformed and missing event IDs/types, wrong-order event, non-integer/bool refund values, partial then exact full refund, cumulative over-refund, missing reconciliation fields, simultaneous amount/status mismatches, mixed ID sorting, and internal/provider amount-field mapping.
- Remaining failures or known limitations: none in the final local test run. Reconciliation uses the last row if an input contains duplicate order IDs; the current output contract has no duplicate-record bucket. The event ledger is in-memory and is not persisted across process restarts. The final verification used Python 3.13.5; the Windows Python 3.14.7 baseline was not rerun after changes.
