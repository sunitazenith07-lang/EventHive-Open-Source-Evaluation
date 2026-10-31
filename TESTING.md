# TESTING.md — Required submission

Complete this file with test evidence from your own work. Include at least five edge cases. Do not claim a test passed unless you ran it.

## Test command and environment
- Python version: 
- Command run:
- Actual test summary:

## Edge-case evidence

| # | Case / input | Expected behaviour | Actual result | Test name or evidence |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

## Regression tests added
List the defects fixed and the tests added to prevent them from returning.

## Remaining failures or limitations
List any known failing tests or unresolved behaviours honestly.

TEST 1--

=============================================================== test session starts ================================================================
platform darwin -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0
rootdir: /Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation
configfile: pyproject.toml
testpaths: tests
collected 0 items / 2 errors                                                                                                                       

====================================================================== ERRORS ======================================================================
_________________________________________________ ERROR collecting tests/test_acceptance_matrix.py _________________________________________________
ImportError while importing test module '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/tests/test_acceptance_matrix.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_acceptance_matrix.py:3: in <module>
    from service import apply_order_event, reconcile_orders
service.py:4: in <module>
    from service import apply_order_event, reconcile_orders
E   ImportError: cannot import name 'apply_order_event' from 'service' (consider renaming '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/service.py' if it has the same name as a library you intended to import)
_____________________________________________________ ERROR collecting tests/test_contract.py ______________________________________________________
ImportError while importing test module '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/tests/test_contract.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_contract.py:2: in <module>
    from service import apply_order_event, reconcile_orders
service.py:4: in <module>
    from service import apply_order_event, reconcile_orders
E   ImportError: cannot import name 'apply_order_event' from 'service' (consider renaming '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/service.py' if it has the same name as a library you intended to import)
============================================================= short test summary info ==============================================================
ERROR tests/test_acceptance_matrix.py
ERROR tests/test_contract.py
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
================================================================ 2 errors in 0.07s =================================================================
ujjwalyadav@UJJWALs-MacBook-Air OrderOps-Open-Source-Evaluation % 





TEST 2--

=============================================================== test session starts ================================================================
platform darwin -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0
rootdir: /Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation
configfile: pyproject.toml
testpaths: tests
collected 0 items / 2 errors                                                                                                                       

====================================================================== ERRORS ======================================================================
_________________________________________________ ERROR collecting tests/test_acceptance_matrix.py _________________________________________________
ImportError while importing test module '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/tests/test_acceptance_matrix.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_acceptance_matrix.py:3: in <module>
    from service import apply_order_event, reconcile_orders
E   ImportError: cannot import name 'apply_order_event' from 'service' (/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/service.py)
_____________________________________________________ ERROR collecting tests/test_contract.py ______________________________________________________
ImportError while importing test module '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/tests/test_contract.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_contract.py:2: in <module>
    from service import apply_order_event, reconcile_orders
E   ImportError: cannot import name 'apply_order_event' from 'service' (/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/service.py)
============================================================= short test summary info ==============================================================
ERROR tests/test_acceptance_matrix.py
ERROR tests/test_contract.py
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
================================================================ 2 errors in 0.05s =================================================================
ujjwalyadav@UJJWALs-MacBook-Air OrderOps-Open-Source-Evaluation % 





TEST 3--
=============================================================== test session starts ================================================================
platform darwin -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0
rootdir: /Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation
configfile: pyproject.toml
testpaths: tests
collected 0 items / 2 errors                                                                                                                       

====================================================================== ERRORS ======================================================================
_________________________________________________ ERROR collecting tests/test_acceptance_matrix.py _________________________________________________
ImportError while importing test module '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/tests/test_acceptance_matrix.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_acceptance_matrix.py:3: in <module>
    from service import apply_order_event, reconcile_orders
service.py:4: in <module>
    from service import apply_order_event, reconcile_orders
E   ImportError: cannot import name 'apply_order_event' from 'service' (consider renaming '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/service.py' if it has the same name as a library you intended to import)
_____________________________________________________ ERROR collecting tests/test_contract.py ______________________________________________________
ImportError while importing test module '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/tests/test_contract.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_contract.py:2: in <module>
    from service import apply_order_event, reconcile_orders
service.py:4: in <module>
    from service import apply_order_event, reconcile_orders
E   ImportError: cannot import name 'apply_order_event' from 'service' (consider renaming '/Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation/service.py' if it has the same name as a library you intended to import)
============================================================= short test summary info ==============================================================
ERROR tests/test_acceptance_matrix.py
ERROR tests/test_contract.py
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
================================================================ 2 errors in 0.05s =================================================================
ujjwalyadav@UJJWALs-MacBook-Air OrderOps-Open-Source-Evaluation % 



TEST 4--

status = 'FAILED', payment_status = 'PAID', due = 5000

    @pytest.mark.parametrize("status,payment_status,due", [
        ("PLACED","UNPAID",0), ("PLACED","PAID",0),
        ("ACCEPTED","PAID",0), ("OUT_FOR_DELIVERY","PAID",0),
        ("DELIVERED","PAID",0), ("REJECTED","UNPAID",0),
        ("CANCELLED","UNPAID",0), ("REJECTED","PAID",5000),
        ("CANCELLED","PAID",5000), ("REJECTED","REFUNDED",5000),
        ("CANCELLED","REFUNDED",5000), ("FAILED","PAID",5000),
    ])
    def test_refund_eligibility_matrix(status, payment_status, due):
        order = new_order("O", 5000, status)
        order.update(payment_status=payment_status, refund_due_paise=due)
        result = apply_order_event(order, ev("R", "refund_processed", amount_paise=1000))
        if status in ("REJECTED","CANCELLED") and payment_status == "PAID" and due > 0:
            assert result["refunded_paise"] == 1000
        else:
>           assert result["refunded_paise"] == 0
E           assert 1000 == 0

tests/test_acceptance_matrix.py:87: AssertionError
============================================================= short test summary info ==============================================================
FAILED tests/test_acceptance_matrix.py::test_refund_eligibility_matrix[FAILED-PAID-5000] - assert 1000 == 0
========================================================== 1 failed, 211 passed in 0.07s 



TEST 6--
service.py:226: TypeError
________________________________________________ test_invalid_refund_amounts_are_ignored[2.2] _________________________________________________

amount = 2.2

    @pytest.mark.parametrize("amount", [0, -1, -10, 0.5, True, None, "10", [], {}, 5001, 6000, 10000, -5000, 2.2, False])
    def test_invalid_refund_amounts_are_ignored(amount):
        order = new_order("O", 5000, "CANCELLED")
        order.update(payment_status="PAID", refund_due_paise=5000)
        result = apply_order_event(order, ev("R", "refund_processed", amount_paise=amount))
>       assert result["refunded_paise"] == 0
E       assert 2.2 == 0

tests/test_acceptance_matrix.py:68: AssertionError
=========================================================== short test summary info ===========================================================
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[0.5] - assert 0.5 == 0
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[True] - assert 1 == 0
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[None] - TypeError: '<' not supported between instances of 'NoneType' and 'int'
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[10] - TypeError: '<' not supported between instances of 'str' and 'int'
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[amount7] - TypeError: '<' not supported between instances of 'list' and 'int'
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[amount8] - TypeError: '<' not supported between instances of 'dict' and 'int'
FAILED tests/test_acceptance_matrix.py::test_invalid_refund_amounts_are_ignored[2.2] - assert 2.2 == 0
======================================================== 7 failed, 205 passed in 0.10s ========================================================
ujjwalyadav@UJJWALs-MacBook-Air OrderOps-Open-Source-Evaluation % 



TEST 7--

platform darwin -- Python 3.14.6, pytest-9.2.0, pluggy-1.7.0
rootdir: /Users/ujjwalyadav/Desktop/open_source/OrderOps-Open-Source-Evaluation
configfile: pyproject.toml
testpaths: tests
collected 212 items                                                                                                                                

tests/test_acceptance_matrix.py ............................................................................................................ [ 50%]
............................................................................................                                                 [ 94%]
tests/test_contract.py ............                                                                                                          [100%]

=============================================================== 212 passed in 0.08s ================================================================
ujjwalyadav@UJJWALs-MacBook-Air OrderOps-Open-Source-Evaluation % 


