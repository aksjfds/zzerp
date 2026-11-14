"""Public behavior port for engineering; callers provide the transaction session."""

from zzerp.modules.engineering.appearances import save_product_appearance
from zzerp.modules.engineering.commands import (
    create_product,
    replace_product_bom,
    save_product_process_flow_draft,
    update_product_info,
    update_product_process_flow,
)
from zzerp.modules.engineering.queries import (
    get_product,
    list_product_appearances,
    list_product_options,
    list_products,
)
from zzerp.modules.engineering.references import (
    appearance_names,
    ensure_plan_appearance,
    get_product_reference,
    get_product_references,
    matching_product_ids_query,
    resolve_plan_product,
)
from zzerp.modules.engineering.routes import (
    current_department_orders,
    current_route_references,
    department_route_keys_query,
    handoff_contexts,
    route_department_code,
    validated_plan_routes,
)

__all__ = [
    "create_product",
    "update_product_info",
    "replace_product_bom",
    "update_product_process_flow",
    "save_product_process_flow_draft",
    "save_product_appearance",
    "get_product",
    "list_product_appearances",
    "list_products",
    "get_product_reference",
    "appearance_names",
    "ensure_plan_appearance",
    "get_product_references",
    "resolve_plan_product",
    "matching_product_ids_query",
    "department_route_keys_query",
    "route_department_code",
    "list_product_options",
    "handoff_contexts",
    "current_department_orders",
    "current_route_references",
    "validated_plan_routes",
]
