# approach.md - Required submission

Complete this file in your own words. Be concise and specific to the work you actually performed.

## 1. Baseline
SETUP
-Ran the following commands to initialize the repo and get setup:
1.Forked the repo from git and cloned it
    -cd E:\Aaryaman\Open_Source_Eval
    -git clone https://github.com/<AaryaVaarya>OrderOps-Open-Source-Evaluation.git
2.Set upstream to open pull request
    -git remote add upstream https://github.com/<original-owner>/OrderOps-Open-Source-Evaluation.git
    -git remote -v
3.Created virtual environment
-Already in .gitignore so it won't be committed
    -python -m venv .venv
    -.venv\Scripts\Activate.ps1
4.Getting pytest file to record baseline
    -python -m pip install --upgrade pip
    -python -m pip install -r requirements-dev.txt
    -python -m pytest --version
5.Recording baseline in baseline.txt
    -python -m pytest -q | Tee-Object baseline.txt
6.Creating the working branch
    -git checkout -b fix-order-refund-logic
    -git status
7.Added baseline.txt in .gitignore and checked using
    -git check-ignore -v baseline.txt

TEST_RESULT
-62 failed,150 passed.
Bugs can be reduced to the following sources.
    1.Duplicate events aren’t ignored
        -When an even tis run again, it's ID is added to processed_events_id a second time.
    2.refund_processed doesn’t validate anything.
        -Bad amounts are accepted
        -Ineligible orders are returned
        -There's no cap to the refunds
    3.Status Mismatch
        -order status is not being reported as mismatched if the status on two ends is different
- Demo/output observed:

## 2. Codebase understanding
- Important files and functions inspected:
- Order lifecycle or data flow traced:
- How you confirmed your understanding:

## 3. Investigation and implementation strategy
For each major defect, describe the observed symptom, the hypothesis you tested, evidence from a test/log/example, and the fix chosen.
- Issue 1:
- Issue 2:
- Issue 3 (if applicable):

## 4. Implementation decisions
- Main changes and why:
- Alternatives considered and why rejected:
- Assumptions:

## 5. Verification
- Tests added or changed:
- Commands run and actual results:
- Edge cases verified:
- Remaining failures or known limitations:

Record actual engineering decisions and evidence. Do not claim tests or experiments you did not run.