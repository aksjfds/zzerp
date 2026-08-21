"""Explicit shared-database grants for cross-module ORM projections.

Only the planning read model and production state-machine core may use these
high-value joined projections. Listing every foreign table here keeps that
coupling visible and reviewable. This is read access only: construction and
mutation of persisted records remain restricted to the owning module.
"""


READ_MODEL_ACCESS = {
    "planning": frozenset(
        {
            "customer",
            "customer_order",
            "customer_order_item",
            "department",
            "procedure",
            "product",
            "product_bom",
            "product_process_flow",
            "production_item",
            "production_movement",
            "repository",
            "work_order",
            "work_order_batch",
            "work_order_material",
            "workshop",
        }
    ),
    "production_core": frozenset(
        {
            "customer_order",
            "customer_order_item",
            "department",
            "procedure",
            "product",
            "product_bom",
            "product_process_flow",
            "work_order_batch",
            "work_order_material",
            "workshop",
        }
    ),
    "standard_execution": frozenset(),
    "inventory": frozenset(
        {
            "customer_order",
            "customer_order_item",
            "department",
            "product",
            "product_process_flow",
            "production_plan",
            "production_plan_item",
            "production_item",
            "production_movement",
        }
    ),
}


def may_read_foreign_table(module_name: str, table_name: str) -> bool:
    return table_name in READ_MODEL_ACCESS.get(module_name, ())
