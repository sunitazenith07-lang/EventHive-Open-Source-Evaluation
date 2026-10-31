"""Run the offline OrderOps reconciliation demo."""
from fixtures import sample_events, sample_orders, sample_provider_orders
from service import apply_events, awaiting_refund_csv, reconcile_orders

if __name__=="__main__":
    for name, values in reconcile_orders(sample_orders(),sample_provider_orders()).items():
        print(f"{name}: {values}")
    orders,_=apply_events(sample_orders(),sample_events())
    print("\nawaiting refund:")
    print(awaiting_refund_csv(orders.values()),end="")
