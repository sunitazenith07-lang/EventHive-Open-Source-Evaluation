# Challenges — OrderOps

## 1. Distinguishing replay bugs from refund bugs
The first reported test run showed 62 failures. An initial local attempt addressed event replay by checking whether an event ID was already in `processed_event_ids`. The next reported run still had 41 failures: the duplicate-event change alone could not correct refund validation or reconciliation.

**Evidence:** Failures included `test_invalid_refund_amounts_are_ignored`, `test_refund_eligibility_matrix`, `test_refunds_cannot_exceed_due`, and `test_reconciliation_status_mismatch_matrix`.

**Resolution:** The fix handles idempotency, validates refund amount and eligibility, and compares reconciliation statuses as well as amounts.

## 2. Refund type pitfalls
The starter code performed `out["refunded_paise"] += event.get("amount_paise", 0)` without checking the type. This caused `TypeError` for `None`, strings, lists, and dictionaries. A boolean is also a subclass of `int` in Python and could be incorrectly treated as a refund amount.

**Resolution:** Only strictly typed integers greater than zero and within the remaining due are accepted. Ineligible events leave refund counters unchanged.

## 3. Confusing stale test output with the current branch
A run on local `main` still showed the older implementation and failures. `git status` identified a modified local `service.py`, and `git branch --show-current` showed `main`.

**Resolution:** The earlier local edit was saved with `git stash`, the remote fix branch was fetched and checked out, and pytest was rerun. The later result was 212 passes.

## 4. Shell output pasted into PowerShell
The terminal returned a `ParserError` when previously printed pytest output (including `from _pytest.python import CallSpec2` and the `PS ...` prompt) was pasted as if it were a command. This was not an OrderOps application bug.

**Resolution:** Use only executable commands at the prompt, not explanatory output or an existing terminal prompt.

## 5. Remaining considerations
- The installed `anyio` plugin emits a deprecation warning regarding pytest 10. It did not cause a visible failure in the observed runs.
- Hidden tests, malformed order records, and out-of-order payment events could warrant further investigation.
- The code and notes were prepared with AI assistance; evaluation-policy compliance must be checked honestly before submission.
