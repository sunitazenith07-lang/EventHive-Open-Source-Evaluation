# Testing Notes

## Running the project

I used Python and pytest to test the project locally. The dependencies were installed inside a virtual environment.

To install the dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

To run all the tests:

```bash
python -m pytest -q
```

To run the application:

```bash
python -m main
```

## What I tested

### 1. Order status changes

I checked how an order moves through its normal lifecycle:

- PLACED to ACCEPTED
- ACCEPTED to OUT_FOR_DELIVERY
- OUT_FOR_DELIVERY to DELIVERED

I also checked rejection and cancellation. An important case was cancellation after dispatch, because an order that has already gone out for delivery should not become CANCELLED.

### 2. Duplicate events

I tested what happens when the same event is received more than once.

The event ID should only be processed once. This is particularly important for payment and refund notifications, since the same notification may be delivered again.

### 3. Refund calculations

This was one of the main areas I investigated.

The tests cover:

- Refunds on unpaid orders.
- Refunds on cancelled and rejected orders.
- Zero and negative amounts.
- Decimal, string and Boolean amounts.
- Refunds greater than the outstanding balance.
- Multiple partial refunds.
- Completion of a full refund.
- Payment confirmation arriving after cancellation.

I also checked that a partial refund doesn't incorrectly change the payment status to REFUNDED.

### 4. Reconciliation

I checked how internal order records are compared with provider records.

The tests cover missing records on either side, different amounts, different statuses and records where both the amount and status differ.

I also checked duplicate order IDs, missing identifiers and malformed comparison values.

### 5. Input validation

I tested malformed events, unsupported event types, missing event IDs and invalid refund payloads.

The original order should also remain unchanged when an event is processed, since the service is expected to return an updated copy.

## Some edge cases I specifically checked

| Case | Expected behaviour |
|---|---|
| Same event received twice | It should not be applied twice |
| Cancellation after dispatch | Delivery status should remain unchanged |
| Refund on an unpaid order | Refund should not be processed |
| Negative refund amount | Should be rejected |
| Refund greater than the remaining balance | Entire refund event should be rejected |
| Partial refund | Payment should remain PAID |
| Full refund | Payment should become REFUNDED |
| Late payment after cancellation | A refund obligation should be created |
| Duplicate order ID | Reconciliation should reject the input |
| Missing order ID | Reconciliation should reject the input |

## Test results

In my latest full local test run, all 254 collected tests passed.

```text
254 passed
```

I reran the test suite after the changes to check that earlier functionality had not been broken.

## Limitations

This project uses synthetic records and runs locally. I haven't tested it against a real payment provider, production database or live webhook service.

The tests establish the behaviour of this offline implementation, not the reliability of a production payment system.