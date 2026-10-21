"""Run the offline OrderOps reconciliation demo."""
from fixtures import sample_orders, sample_provider_orders
from service import reconcile_orders

if __name__=="__main__":
    for name, values in reconcile_orders(sample_orders(),sample_provider_orders()).items():
        print(f"{name}: {values}")
