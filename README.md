# OrderOps — Order Failure, Cancellation & Refund Reconciliation

Zenith School of AI | Individual Open-Source Evaluation | Python 3.10+

This simulated service models failure and refund edge cases in a food-delivery platform. It is inspired by common food-delivery operations; it is not Zomato's internal software and does not connect to real payments or customers.

## Start
1. Read STUDENT_PROBLEM_STATEMENT.md.
2. Run `python -m pip install -r requirements-dev.txt`
3. Run `python -m pytest -q`
4. Run the sample: `python -m main`

Some visible tests are expected to fail on the untouched starter. Fix the behaviour; don't delete or weaken tests. GitHub Actions runs on pushes, pull requests, and manual dispatch, and reports pass/fail counts. The check stays red until the visible tests pass.

## Key files
- `service.py` — order event and refund logic.
- `models.py` — starter order records.
- `fixtures.py` and `data/records.json` — synthetic records.
- `tests/test_contract.py` — visible contract tests.
- `.github/workflows/tests.yml` — automated pull-request checks.

Fork this repository and open a pull request against this original repository. Do not merge your PR. Be ready to explain and make a small live change. See CONTRIBUTING.md for the AI-integrity policy.
