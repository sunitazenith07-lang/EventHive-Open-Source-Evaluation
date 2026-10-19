# EventHive: Campus event registration, capacity and attendee tracking

**Zenith School of AI | Open-Source Evaluation | Python 3.10+ | JSON | GitHub**

## Challenge
EventHive is a Python application for managing campus events, registration counts, attendee records and venue capacity. Your task is to understand the existing code, fix three issue tickets announced by organisers at kick-off, strengthen search and filtering, implement one optional feature, add tests and explain your decisions. Improve the existing project; do not rebuild it from scratch.

## Start-up
Run these commands from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m main
```

Inspect README.md, models.py, service.py, fixtures.py, data/ and tests/test_contract.py before editing. Create ARCHITECTURE.md explaining the data model, program flow, storage design, a diagram and three improvements grounded in the code.

## Mandatory work
1. Reproduce and fix the three issue tickets released at kick-off. Add a regression test for each.
2. Implement case-insensitive search that trims surrounding spaces, and combined category and status filters. Invalid filters and no-results states must be handled safely.
3. Implement and test at least one additional feature below:
   - Waitlist: record waitlisted attendees when full and promote the next eligible person when a confirmed registration is cancelled.
   - Capacity dashboard: show event capacity, confirmed registrations, spaces remaining and waitlist size.
   - Duplicate-registration warning: detect duplicate attendee emails after normalising whitespace and case.
4. Keep PROJECT_NOTES.md and README.md current. Document at least five meaningful test scenarios in TESTING.md.
5. Work on focused branches and pull requests. Do not remove, skip, weaken or bypass the supplied tests.

## Test suite
The public suite contains 110 visible test cases. The untouched starter is intended to begin at 86 passing and 24 failing because of deliberate defects. The final evaluation also includes 90 private checks, for 200 automated cases total; private checks are not in this public repository. A green visible suite alone does not guarantee full credit.

## GitHub workflow
Use fix/issue-<number>-<summary> for each bug and feature/<short-name> for a feature. Pull requests should include the root cause, what changed, issue reference, tests run and known limitations. Watch the Actions tab for the visible test results.

## Submission
Submit your repository/fork URL, pull-request links, README.md, ARCHITECTURE.md, TESTING.md, PROJECT_NOTES.md, a summary of bugs fixed, feature notes and a two-minute demo. If AI tools are used, complete AI_USAGE.md: state the tool/model, purpose, what you verified or changed yourself, the result and any displayed credit/token count (or “not available”). Do not include secrets or private personal data. You must be able to explain and modify your code during the viva.

## Evaluation — 100 marks

| Criterion | Marks |
|---|---:|
| Codebase understanding | 15 |
| Problem solving and root-cause analysis | 25 |
| Working prototype and requested features | 20 |
| Code quality | 10 |
| Testing and edge cases | 10 |
| Demo, communication and viva | 20 |
| **Total** | **100** |

All 300 students are assessed using the same rubric. The top 270 students will be shortlisted by final score, subject to minimum competency criteria announced by organisers. Follow the event schedule and the latest official announcement for deadlines, code freeze and demo timings.
