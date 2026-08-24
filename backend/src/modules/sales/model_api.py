"""Read-only query-model surface for sales persistence."""

from modules.sales.persistence import Customer, CustomerOrder, CustomerOrderItem

__all__ = ["Customer", "CustomerOrder", "CustomerOrderItem"]
