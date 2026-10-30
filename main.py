"""Run the offline OrderOps reconciliation demo."""
import json
from collections import Counter
from pathlib import Path

from fixtures import sample_orders, sample_provider_orders
from service import process_events, reconcile_orders

DATA = Path(__file__).resolve().parent / "data" / "records.json"

if __name__=="__main__":
    for name, values in reconcile_orders(sample_orders(),sample_provider_orders()).items():
        print(f"{name}: {values}")

    if DATA.exists():
        data = json.loads(DATA.read_text())
        state, rejected = process_events(data["orders"], data["events"])
        print(f"\nrecords.json: {len(data['events'])} events, "
              f"{len(data['events']) - len(rejected)} applied, {len(rejected)} rejected")
        for reason, count in sorted(Counter(r["reason"] for r in rejected).items()):
            print(f"  {reason}: {count}")
        early = [r for r in rejected if r["out_of_order"]]
        print(f"out-of-order (arrived too early): {len(early)}")
        for r in early:
            print(f"  #{r['index']} {r['event_id']} {r['order_id']} ({r['reason']})")
        report = reconcile_orders(data["orders"], data["provider_records"])
        print("records.json reconciliation: "
              + ", ".join(f"{k}={len(v)}" for k, v in report.items()))
