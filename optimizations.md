# Optimizations and Possible Improvements

While working on this project, I came across a few areas where the implementation could be improved further. Some of these improvements are already included in the current implementation, while others would be useful if the application were extended beyond this offline exercise.

## 1. Improvements made during the implementation

### Event idempotency

The original implementation did not check whether an event ID had already been processed.

I added a duplicate-event check before processing an event. This prevents the same notification from applying its effects multiple times.

This is particularly important for refund events because processing the same refund twice could result in an incorrect refunded amount.

### Refund validation

I added checks for refund eligibility and the refund amount before updating the order.

The implementation now checks the outstanding balance instead of blindly adding incoming refund amounts.

This also prevents Boolean values from being accepted as integer paise, which is something worth considering in Python because `bool` is a subclass of `int`.

### Reconciliation improvements

The original reconciliation logic compared amounts using the same field name for both systems.

I added normalization for the different amount fields used by internal and provider records.

I also separated amount comparisons from status comparisons so that both discrepancies can be reported for the same order.

### Duplicate order ID detection

The original dictionary construction could silently overwrite records with duplicate order IDs.

I added explicit duplicate detection so conflicting records are not silently lost during reconciliation.

### Input validation

I also added validation for missing event identifiers, unsupported event types, malformed refund payloads and invalid reconciliation identifiers.

These checks help prevent incomplete or unexpected inputs from silently changing business state.

## 2. Improvements that could be considered in a larger system

### Persistent event history

The current implementation keeps processed event IDs inside the order record.

This is sufficient for the supplied offline exercise, but a larger application would need persistent storage so event history survives application restarts.

A database table with a uniqueness constraint on event IDs could help prevent duplicate processing across multiple application instances.

### Atomic refund updates

In a production application, updating the refunded amount and recording the corresponding event should happen atomically.

Otherwise, a failure between these operations could cause the same event to be applied again when a provider retries its notification.

A database transaction would help protect these updates.

### Better handling of out-of-order events

Payment and order notifications do not necessarily arrive in the order in which the underlying events occurred.

A larger implementation could use event timestamps, sequence numbers or a pending-event mechanism to identify events that arrive out of order.

This would need careful handling so that an invalid transition is not silently converted into a valid one.

### More detailed reconciliation reporting

The current report identifies missing records, amount differences and status differences.

A future version could include more diagnostic information, such as:

- Internal and provider amounts.
- Internal and provider statuses.
- The reason a record was flagged.
- A timestamp indicating when reconciliation was performed.

This would make it easier to investigate mismatches.

### Better logging and error reporting

For this exercise, the implementation uses simple return values and validation errors.

A larger application could include structured logging to record rejected events, duplicate notifications and reconciliation failures.

This would make debugging and investigating payment-related problems easier.

### Broader automated testing

Additional tests could cover concurrent refund notifications, application restarts, conflicting duplicate event IDs and more complex event-ordering scenarios.

These cases become particularly important when the service moves from local execution to a distributed environment.

## 3. Why I kept the implementation simple

I did not add a database, external payment integration or a distributed event-processing system.

The project is designed as an offline exercise with synthetic data, and introducing additional infrastructure would make the implementation unnecessarily complicated.

I focused on correcting the existing behaviour, protecting refund calculations and making reconciliation more reliable.

The future improvements above are possibilities for a larger application rather than features that are currently implemented.

## Conclusion

The main improvement was not adding more infrastructure, but making the existing service safer and more predictable.

The implementation now has stronger validation around events, refunds and reconciliation, while keeping the original project structure relatively small.