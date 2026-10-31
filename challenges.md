# Challenges Faced During Development

While working on OrderOps, I came across a few issues that took some investigation to understand. Some were straightforward bugs, while others only became apparent after running the larger test suite.

## 1. Understanding the event flow

Initially, I found it slightly difficult to understand how order status and payment status were connected.

For example, a cancelled order does not necessarily mean that the payment has already been refunded. The order can be CANCELLED while the payment is still PAID because the refund has not been completed.

I had to keep these two states separate when investigating the refund logic.

## 2. Duplicate event processing

One of the first issues I investigated was event idempotency.

The original implementation added event IDs to `processed_event_ids` but did not check whether an event had already been processed.

This meant that a repeated refund notification could increase the refunded amount again.

I added an event ID validation and duplicate check before processing the event.

I also tested this using the existing duplicate-event test.

## 3. Finding a refund field-name mistake

This was one of the more interesting debugging issues.

At one point, the refund completion condition was using:

`refunded_due_paise`

The actual field name in the order model was:

`refund_due_paise`

Because the code used dictionary `.get()` with a default value of zero, the incorrect field name did not immediately produce an exception.

Instead, the comparison used zero and caused partial refunds to be incorrectly marked as complete.

It took some investigation of the test failures to identify the incorrect field name.

After correcting it, the partial-refund tests passed.

## 4. Valid refund events were being ignored

During another change, I added validation for refund event amounts.

However, I accidentally placed a `return out` immediately after the validation section.

This meant that even valid refund events returned before reaching the actual refund-processing logic.

The full test suite showed a large number of refund-related failures.

After checking the control flow, I found the misplaced return statement and removed it while keeping the invalid-amount checks.

This restored valid partial and full refund processing.

## 5. Protecting against excessive refunds

Another issue was that the original code simply added the incoming refund amount to the existing refunded amount.

It did not calculate how much was still outstanding.

I added validation for positive integer amounts and checked the remaining refund balance before applying a refund.

I also made sure that Boolean values were rejected, since Python treats Boolean values as a subclass of integers.

## 6. Reconciliation was missing status comparisons

Initially, the reconciliation function compared amounts but did not properly compare order statuses.

This meant an order could have the correct amount but a completely different status in the provider records and still be classified as matched.

I changed the comparison so that amount and status differences are reported independently.

## 7. Different amount field names

I also discovered that internal records used `total_paise`, whereas provider records used `amount_paise`.

The original reconciliation function tried to read the same field from both records.

This caused false amount mismatches.

I added normalization so that the two representations could be compared using the correct fields.

## 8. Duplicate order IDs

The original dictionary comprehension used in reconciliation silently overwrote earlier records when the same order ID appeared more than once.

I investigated this and added duplicate ID detection.

During testing, I also encountered a small error in the exception message itself. The detection logic worked, but the wording did not match what the regression test expected. Correcting the message resolved that test.

## 9. Event validation and cancellation regression

When adding validation for supported event types, some cancellation transition tests unexpectedly started failing.

I checked the failing transition matrix and traced the problem to the event validation path.

After correcting the handling of supported cancellation events, the cancellation tests passed again.

This reminded me that a change to event validation can affect otherwise unrelated order transitions.

## 10. Git whitespace warnings

Before preparing the changes for submission, I ran `git diff --check`.

It reported trailing whitespace on several lines in `service.py`.

I used VS Code's Trim Trailing Whitespace command to clean them up and reran the check.

The second run produced no whitespace warnings.

## What I learned

The biggest lesson from this work was that passing one test does not necessarily mean an entire feature is correct.

I found several cases where a small change affected other parts of the application. Running both individual regression tests and the full test suite helped identify these problems.

I also learned to pay more attention to dictionary field names, function return placement, event ordering and the difference between order state and payment state.

These details are especially important when dealing with financial operations because an incorrect refund calculation can cause more serious problems than an ordinary status mismatch.