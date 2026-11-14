"""Public behavior port for sales; callers provide the transaction session."""

from zzerp.modules.sales.customers import (
    list_customers,
)
from zzerp.modules.sales.references import (
    customer_ids_matching_name_query,
    customer_names_by_ids,
    resolve_customer,
)

__all__ = [
    "list_customers",
    "resolve_customer",
    "customer_names_by_ids",
    "customer_ids_matching_name_query",
]
