# challenges.md - COMPULSORY submission

## 1. Challenge or confusing behaviour
-ORD-101 still should up a mismatch in demos even though the amount was 45900 paise on both sides


## 2. Evidence
-Demo output after fix 3:
    -matched: []
    -amount_mismatches: ['ORD-101']
-Both records had 45900, but amount being compared was none.

## 3. What I tried
-Ran the demo after every fix
-Printed both ORD-101 records and saw different field names: total_paise on ours, amount_paise on the provider's.
-models.py and records.json both use total_paise which affects the orders.
-The tests use amount_paise on both sides

## 4. Resolution
-reconcile_orders only looked for amount_paise, so our orders always had an amount of None.
-Added a small helper that reads amount_paise, or total_paise if it's missing.
-This fixes the cause, since both real amounts are now compared.
-Didn't rename the field in models.py, since that would change the data model.

## 5. Proof and regression prevention
-The demo now shows ORD-101 as matched.
-Added two tests: same amount under different field names (match), and different amounts (mismatch).
-Could still break: two records with no amount field would both read as None and look matched.

## 6. Unresolved challenge or next step
-Records with no amount aren't handled yet. I'd report them as invalid rows, like rows with no order ID.
-Out-of-order events are still ignored. I'd first check how often that happens in records.json.