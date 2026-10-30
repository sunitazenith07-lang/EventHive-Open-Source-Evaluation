# challenges.md

## 1. Challenge or confusing behaviour
**"Replay the whole dataset twice" was not idempotent.** A property test ran all 219 events in `data/records.json` through `process_events`, then ran them again on the result, expecting identical state. It failed on one order, which conflicted with requirement 3.

Two smaller confusions:
- The dataset deliberately contains repeated event ids, yet the first pass reported zero `duplicate_event` rejections.
- After the first rewrite of `service.py` the test count did not move at all (still 62 failed).

## 2. Evidence
```
AssertionError: assert twice == once
Differing items:
{'ORD-1007': {... 'status': 'REJECTED', 'payment_status': 'REFUNDED', ...}}
  != {'ORD-1007': {... 'status': 'REJECTED', 'payment_status': 'PAID', ...}}
```
Step trace of ORD-1007 (starts PLACED / PAID, total 1000):
```
ORD-EV-0007 refund_processed 1000 -> refund_not_eligible  PLACED   PAID  due 0    refunded 0
ORD-EV-0157 restaurant_rejected   -> applied              REJECTED PAID  due 1000 refunded 0
```

## 3. What I tried
1. Traced the single differing order event by event (above). The refund arrives *before* the rejection, so on pass 1 it is correctly refused.
2. Checked the design: rejected events are intentionally not added to `processed_event_ids`. On pass 2 the order is REJECTED / PAID with 1000 due, so the same refund event is now valid and applies once.
3. Weighed the alternative of recording every well-formed id, even when rejected. That makes the whole-stream replay identical, but it would permanently drop a real refund notification that arrived early. That is a worse failure for money handling.
4. For the missing duplicates: listed every repeated id with its rejection reason. All 11 pairs hit orders where the first copy is itself invalid. For example, ORD-1018 is already DELIVERED, so both `cancel_requested` copies are `invalid_transition`. With nothing recorded, the second copy reports the same underlying reason, not "duplicate".
5. For the unchanged test count: `python -c "import service; print(service.__file__)"` showed Python was importing a different checkout from the one that had been edited. The repository was moved so the edited file was the one under test. The next run went from 62 failed to 212 passed.

## 4. Resolution
- The code was right. The test was asserting the wrong property. Requirement 3 says replaying an event must not change state *a second time*, and an event that was refused never changed state a first time.
- The test now checks three stricter things:
  - replaying every *applied* event changes nothing, and every rejection is `duplicate_event`;
  - a third full pass equals the second (a fixed point);
  - refunds stay within `0 ≤ refunded ≤ due` on every pass.
- The dataset-reason assertion now lists the reasons that genuinely occur. Duplicate handling for applied events is proven by the replay step and by `test_replayed_refund_is_counted_once`.

## 5. Proof and regression prevention
- `test_dataset_replay_of_applied_events_is_idempotent_and_refunds_stay_in_bounds`
- `test_rejected_refund_is_not_recorded_so_a_redelivery_can_apply_later`
- `test_replayed_refund_is_counted_once`, `test_replay_with_conflicting_payload_is_still_ignored`

Still at risk: if someone later starts recording rejected ids, the early-refund test will fail, by design. That forces the trade-off to be revisited deliberately.

## 6. Unresolved challenge or next step
- An early event currently has no queue. It is only applied if the provider redelivers it.
- A real service would park out-of-order events per order and retry them after each successful transition. This is close to the "flag out-of-order events" stretch item, which was not attempted.
- To validate it: re-run the ORD-1007 trace and expect the refund to apply on the first pass.
