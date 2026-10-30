# OrderOps, step by step

> Codex performed and documented the work below with evaluator permission for AI
> assistance, confirmed by the student on 30 October 2026. See AI_ASSISTANCE.md for
> the contribution record.

## 1. What is on your computer and on GitHub

The original repository belongs to `sunitazenith07-lang`. Your fork belongs to
`omparida-wq`. A fork is a separate repository on GitHub. Your Desktop clone is a
local copy of your fork. Editing local files changes neither GitHub repository until
you commit and push those changes.

The Desktop folder is:

```text
/Users/omprakashparida/Desktop/OrderOps-Open-Source-Evaluation
```

Its `origin` remote is your fork:

```text
https://github.com/omparida-wq/OrderOps-Open-Source-Evaluation.git
```

The original checkout was on `main` at commit
`e006d241e3d8ddf6520021a6ab554306a31a200b`. A new branch named
`fix/orderops-refund-safety` contains this reference implementation. A branch lets you
review the changes separately from the untouched starting point.

The branch was created with:

```bash
git switch -c fix/orderops-refund-safety
```

You do not need to run that command again: the branch already exists locally.

## 2. Understand the Python environment

The `.venv` directory contains the project-specific Python environment. Activating
it makes `python` and `pip` refer to that environment in the current terminal. Your
Desktop environment uses Python **3.14.7** and pytest **9.2.0**.

To return to the project in a new terminal:

```bash
cd ~/Desktop/OrderOps-Open-Source-Evaluation
source .venv/bin/activate
```

`cd` changes directory. `source` loads the activation script into the current shell.
The `(.venv)` prefix in your screenshot indicates that activation succeeded.
The only development requirement is pytest. The business logic itself uses Python's
standard library and does not call a payment service.

## 3. Establish what failed before editing

The starting command was:

```bash
python -m pytest -q
```

`python -m pytest` runs pytest using the selected Python interpreter. `-q` asks for
compact output. The result was **62 failed, 150 passed** across 212 original cases.
A red failure means an assertion did not match, or code raised an unexpected error;
it does not by itself imply an installation problem.

Your focused duplicate test then called the service twice with the same event. The
expected recorded IDs were `['e1']`; the actual list was `['e1', 'e1']`. That is a
small reproduction of one business-logic defect. Running a test observes behavior;
editing the implementation is what changes the behavior.

The baseline logs and XML are preserved in `evidence/baseline-tests.txt` and
`evidence/baseline-tests.xml`. Recording a baseline shows what was broken before
the change, rather than attributing every later failure to a new edit.

## 4. Understand the dictionaries

`models.new_order()` returns a dictionary like this:

```python
{
    "order_id": "EXAMPLE",
    "total_paise": 1000,
    "status": "PLACED",
    "payment_status": "UNPAID",
    "refund_due_paise": 0,
    "refunded_paise": 0,
    "processed_event_ids": [],
}
```

| Field | Meaning |
|---|---|
| order_id | Identifies the order. |
| total_paise | The original order value in integer paise. |
| status | The food-order lifecycle state. |
| payment_status | Whether payment is unpaid, paid, or fully refunded. |
| refund_due_paise | The total refund obligation. |
| refunded_paise | The amount already processed toward that obligation. |
| processed_event_ids | IDs already consumed for this order. |

One rupee is 100 paise, so 1000 paise is Rs 10. Whole-number paise avoid fractional
currency calculations. The order's `status` and its `payment_status` describe
separate things: an order can be CANCELLED while its payment is still PAID because
the refund has not finished.

An event is another dictionary, such as:

```python
{"event_id": "p1", "type": "payment_confirmed"}
```

A refund event also carries `amount_paise`. The public function applies one event
to one supplied order. If an event includes `order_id`, it must match that order.
A program reading a whole event stream must route events to existing orders first.

## 5. Read service.py from top to bottom

Only `service.py` changes production behavior. The model, fixtures, main module,
original tests, dataset, and GitHub Actions workflows remain unchanged.

### The import and constants: lines 1-17

`deepcopy` makes an independent copy of the input order, including nested lists and
metadata. A shallow copy would still share the history list and could accidentally
change the caller's original order when appending an ID.

The constants list allowed order states, payment states, refundable order states,
and event types. `_TRANSITIONS` maps an event and starting state to a destination:

```python
"dispatch_started": {"ACCEPTED": "OUT_FOR_DELIVERY"}
```

Reading this entry tells you that dispatch can start from ACCEPTED. There is no entry
from PLACED, so a premature dispatch does not move the order.

### The identifier helper: lines 20-21

`_identifier()` checks for a string that is not empty or only whitespace. It is used
for order IDs, event IDs, and non-empty reconciliation statuses. It validates an
identifier but does not rewrite or trim the stored ID.

### The money helper: lines 24-26

`_paise()` accepts a non-negative integer. It uses `type(value) is int` because
Python treats booleans as a subclass of integers. Accepting `True` as one paise would
be an incorrect interpretation of malformed financial input.

This helper permits zero for balances and order totals. The refund branch adds a
separate `amount > 0` condition because an actual refund must be positive.

### Snapshot validation: lines 29-45

`_valid_order()` checks the required identifiers, known state values, money types,
history shape, and these numeric bounds:

```text
0 <= refunded_paise <= refund_due_paise <= total_paise
```

Missing optional fields can use safe defaults: UNPAID, zero balances, and an empty
history. Required order ID, total, and status must be valid. Unsafe snapshots are
returned unchanged rather than having their money guessed or silently repaired.
This is structural and numeric validation; it is not a complete historical ledger
migration or a detector for every possible cross-field inconsistency.

### Event boundary and replay check: lines 48-70

`apply_order_event()` first checks that the supplied order is a dictionary. A caller
passing another kind of object receives a clear TypeError. It then copies the order.
An unsafe snapshot or non-dictionary event returns that independent copy unchanged.

Next it checks the event's ID and type, optional target order ID, and recorded IDs.
A malformed envelope, unknown type, or wrong target cannot alter the order.
If the event ID is already recorded, the function returns immediately. This is
**idempotency**: applying the same notification again has no second effect.

The check happens before any lifecycle or money update. Checking only before
appending the ID would still allow a duplicate refund to change money twice.
Reusing an ID with a different payload also has no second effect: IDs identify the
notification, not just its current contents.

### Defaults: lines 72-75

`setdefault()` supplies optional fields only when they are absent. It preserves
existing values. Defaults are applied only after the event envelope and snapshot
have been checked, so an invalid event does not normalize or rewrite legacy input.

### Payment confirmation: lines 77-82

A valid confirmation changes UNPAID to PAID. It does not change the food-order
status, and it cannot turn REFUNDED back into PAID.

A delayed payment can arrive after an unpaid order was cancelled or rejected. In
that case the terminal order stays terminal and the refund obligation becomes its
full order value. That policy prevents a late successful payment from being left
without an amount due for refund.

### Lifecycle transitions: lines 83-88

The function looks up the destination for the current event and state. When no entry
exists, it leaves the lifecycle unchanged. The allowed moves are:

```text
PLACED --restaurant_accepted--> ACCEPTED --dispatch_started--> OUT_FOR_DELIVERY
PLACED --restaurant_rejected--> REJECTED
PLACED --cancel_requested-----> CANCELLED
ACCEPTED --cancel_requested---> CANCELLED
OUT_FOR_DELIVERY --order_delivered--> DELIVERED
```

There is no cancellation move after dispatch. If an eligible transition cancels or
rejects a paid order, the total order value becomes the refund obligation.
A restaurant rejection after acceptance is ignored, matching the supplied tests.

### Refund processing: lines 89-99

The remaining refundable balance is calculated as:

```python
remaining = out["refund_due_paise"] - out["refunded_paise"]
```

The update is allowed only when all four conditions hold:

1. Order state is CANCELLED or REJECTED.
2. Payment state is PAID.
3. The amount is a strict integer paise value.
4. `0 < amount <= remaining`.

An excessive amount is rejected as a whole. It is not clipped to the balance, since
the service should not reinterpret what the provider said happened. Once a valid
amount is added, payment becomes REFUNDED only when cumulative refunded money equals
the full refund obligation. Otherwise it remains PAID.

### Recording the event: lines 101-102

The recognized, addressed event ID is recorded once before returning the result.
In this reference, that includes known events whose requested transition or refund
was rejected. For example, an early refund cannot become effective just by replaying
its original ID after later cancellation. A corrected notification needs a new ID.

This is an explicit policy choice because the brief does not specify the retry
semantics of every rejected notification. Malformed envelopes and unknown targets
are not recorded. A production system would also need durable storage and structured
rejection reasons; this list alone is not a complete production audit log.

### Summary normalization: lines 105-128

`_summary_index()` converts each validated row into a pair `(amount, status)` keyed
by order ID. Internal domain orders use `total_paise`; provider rows use
`amount_paise`. The helper accepts those documented shapes and rejects conflicting
values when a row supplies both keys.

This fixes the starter demo's false amount discrepancies. Previously the service
read `amount_paise` from the internal order, where that key did not exist.

Malformed summary collections or rows raise ValueError. Identical summaries with
the same ID collapse to one entry. Duplicate IDs with different amounts or statuses
raise ValueError instead of silently retaining whichever row happened to come last.
Neither input collection is modified, and no misleading partial report is returned.

### Reconciliation: lines 131-158

Both sides are validated and indexed. The function iterates through the sorted union
of their order IDs and fills five lists:

| Output list | When an ID goes into it |
|---|---|
| matched | Both sources contain the ID and both amount and status agree. |
| missing_from_provider | Only the internal source contains it. |
| missing_from_internal | Only the provider source contains it. |
| amount_mismatches | Both contain it, but their amounts differ. |
| status_mismatches | Both contain it, but their order statuses differ. |

The amount and status checks are independent `if` statements. If both differ, the
same ID belongs in both mismatch lists. An `elif` would hide one discrepancy.
Sorting means shuffling input rows does not shuffle the report.

This comparison concerns order values and the order `status` field. Provider
references and `payment_status` are not additional reconciliation dimensions.

## 6. Follow one full refund example

The executed example starts with an order worth 1000 paise:

| Step | Notification | Order state | Payment state | Total due | Already refunded | Still refundable |
|---|---|---|---|---:|---:|---:|
| Start | New order | PLACED | UNPAID | 0 | 0 | 0 |
| 1 | p1: payment_confirmed | PLACED | PAID | 0 | 0 | 0 |
| 2 | c1: cancel_requested | CANCELLED | PAID | 1000 | 0 | 1000 |
| 3 | r1: refund 400 | CANCELLED | PAID | 1000 | 400 | 600 |
| 4 | Replay r1 | CANCELLED | PAID | 1000 | 400 | 600 |
| 5 | r2: refund 600 | CANCELLED | REFUNDED | 1000 | 1000 | 0 |

The due amount stays 1000 after cancellation; it means the total obligation. The
remaining amount is computed by subtraction. This makes partial and complete refunds
unambiguous. The actual dictionaries are saved in `evidence/walkthrough.json`.

## 7. Understand the tests and results

The two original test files remain byte-for-byte unchanged. Their 212 cases cover
the supplied transition, refund, and reconciliation matrices. A new file,
`tests/test_regressions.py`, adds 96 collected cases. Pytest parametrization runs one
test function repeatedly with different inputs, which is why case count is larger
than the number of function definitions.

The regressions check multi-event refund sequences, conflicting replays, delayed
payments, preservation of REFUNDED state, malformed envelopes, wrong target IDs,
unsafe snapshots, deep-copy isolation, duplicate summaries, both mismatch categories,
all permutations of a small report, the larger dataset, and the actual main module.

Final result in the Desktop environment:

```text
308 passed in 0.11s
```

Those 308 cases include all 212 original cases and 96 additions. No original test
was deleted, skipped, or weakened. The test and PDF-building workflows are unchanged.
The large dataset report contains 107 matches, 12 missing from the provider,
25 missing internally, 20 amount mismatches, and 12 status mismatches. The discrepancy
categories can overlap, so adding their counts is not a count of distinct orders.

To rerun the full suite:

```bash
python -m pytest -q
```

To inspect one test with detail:

```bash
python -m pytest tests/test_contract.py::test_duplicate_event_is_idempotent -vv
```

## 8. Understand the demo output

Running `python -m main` uses fixtures.py and prints the reconciliation report:

```text
matched: ['ORD-101']
missing_from_provider: ['ORD-103']
missing_from_internal: ['ORD-104']
amount_mismatches: []
status_mismatches: ['ORD-102']
```

ORD-101 has matching order value and status. ORD-103 exists only internally.
ORD-104 exists only at the provider. ORD-102 has the same value on both sides but
different statuses, so it is a status discrepancy rather than a match.
This demo is reconciliation over synthetic data; it does not initiate refunds.

## 9. Understand the documentation

| File | What it records |
|---|---|
| approach.md | Baseline, source flow, root causes, implementation choices, validation. |
| challenges.md | Actual confusing behavior, evidence, resolution, remaining gaps. |
| optimizations.md | Maintainability and complexity choices, trade-offs, future proposals. |
| TESTING.md | Environment, commands, exact observed results, and edge-case evidence. |
| ORDER_FLOW_NOTES.md | One executed event sequence and its expected/observed states. |
| GUIDE.md | Summary, requirements, diagram, plan, and a compact implementation overview. |
| STEP_BY_STEP.md | This detailed explanation of the work and every service-code block. |
| AI_ASSISTANCE.md | Codex contributions and evaluator permission confirmed by the student. |
| evidence/ | Machine-generated logs and scenario outputs supporting the notes. |

These notes describe the work Codex performed with evaluator permission for AI
assistance, as confirmed by the student. The student's own review and ability to
explain the changes are separate from the recorded implementation and test evidence.

## 10. Understand commit, push, pull request, and CI

A **commit** saves a named Git snapshot locally. A **push** publishes the branch to
your fork on GitHub. A **pull request** asks the original repository to review that
branch. A **draft PR** exposes it for review while making clear it is not ready for
merging. Creating or pushing a branch does not merge it into the original project.

The intended workflow uses these commands after verification:

```bash
git diff --check
git add service.py tests/test_regressions.py README.md AI_ASSISTANCE.md \
  GUIDE.md STEP_BY_STEP.md approach.md challenges.md optimizations.md \
  TESTING.md ORDER_FLOW_NOTES.md evidence
git diff --cached --stat
git commit -m "Fix OrderOps event replay, refund safety, and reconciliation"
git push -u origin fix/orderops-refund-safety
```

`git diff --check` catches whitespace errors. `git add` selects files for the next
commit. `--cached` inspects the selected changes. The push's `-u` records the upstream
branch, so later `git push` can use that destination by default.

The draft PR targets `sunitazenith07-lang/OrderOps-Open-Source-Evaluation:main` from
`omparida-wq:fix/orderops-refund-safety`. Its description records the AI assistance
and the evaluator's permission confirmed by the student. Any personal declaration
about independently explaining or modifying the code is left for the student to
confirm after review. The PR is not merged by this workflow.

The existing GitHub Actions test job uses Python 3.11. Remote results need separate
verification because a successful local Python 3.14 run does not itself prove CI
passed. A first-time-contributor PR may require a maintainer to approve its workflow;
that is distinct from a failing test. The final handoff reports the actual PR/CI state.

## 11. Limits to keep in mind

This service is deliberately offline and in memory. It has no real payment API,
database transactions, durable event history, concurrent-writer protection, provider
signature verification, or complete historical-ledger repair process. Those are
separate production requirements, not implied by passing the exercise's tests.
Python 3.14.7 was run in this clone; an earlier separate reference also passed on
Python 3.12.14. Hidden evaluation tests are unavailable.
