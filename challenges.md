# Challenges and debugging

The main tricky case was separating an invalid event from a valid event that happens to leave visible order fields unchanged. The starter appended event IDs broadly, which could make a later corrected/replayed event look like a duplicate. I changed the handler to return an unchanged deep copy for missing/blank IDs, duplicate IDs, unsupported event types, and illegal transitions; only an event that actually applies is recorded.

Refund notifications required checks against the cumulative amount, not only the incoming notification. A partial refund must leave payment PAID; a repeated notification must not increase refunded_paise; zero, negative, non-integer, and over-due amounts must not be applied. The revised guard checks integer type (excluding bool), positivity, paid status, eligible order status, and refunded + amount <= due.

The baseline evidence was 62 failed, 150 passed; the final visible suite reported 212 passed. This included the reconciliation contract: when equal-amount records have different statuses, the ID must appear in status_mismatches, not matched. No production provider integration is present, so transport retries and concurrent writes remain outside this offline exercise.
