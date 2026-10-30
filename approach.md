# Approach and implementation decisions

## Investigation
The untouched checkout ran on Python 3.14.2. Before editing, python -m pytest -q reported **62 failed, 150 passed**. After installing requirements-dev.txt, I traced event application in service.py, initial records in models.py and fixtures.py, the demo path in main.py, and contract/acceptance coverage in tests/.

## Root causes and solution
apply_order_event copied the order but accepted repeated or malformed event identifiers, changed states without consistently checking eligibility, and applied refunds without enforcing positive amount, outstanding due, or paid/cancelled eligibility. Refund completion was inferred with a loose comparison. reconcile_orders compared amounts but ignored status, so status differences appeared as matches.

I kept the public function signatures and output report keys. Event processing now validates event shape and supported types, checks legal source states, requires a unique non-empty event ID, and only records an ID when its event takes effect. Refunds require a positive integer paise amount and cannot take cumulative refunds above the due amount. Reconciliation compares amount and status independently and only marks a record matched when both agree.

## Validation
After the change, python -m pytest -q reported **212 passed**. The test suite covers transition flow, duplicate IDs, refund bounds and reconciliation. I also ran python -m main; see its recorded result in TESTING.md.
