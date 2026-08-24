"""Authoritative ownership of persisted tables in the modular monolith.

Ownership means schema evolution and write invariants belong to one module.
ORM definitions live in the owning module's ``persistence.py``. Exceptional
shared-database reads must be explicitly registered, while every write API
must remain with the owner instead of creating a second writer.
"""


TABLE_OWNERS = {
    "users": "identity",
    "user_sessions": "identity",
    "customer": "sales",
    "customer_order": "sales",
    "customer_order_item": "sales",
    "product": "engineering",
    "product_version": "engineering",
    "product_bom": "engineering",
    "product_process_flow": "engineering",
    "product_route_task": "engineering",
    "department": "organization",
    "workshop": "organization",
    "procedure": "organization",
    "worker": "workforce",
    "procedure_price": "standard_execution",
    "production_item": "production_core",
    "repository": "production_core",
    "work_order": "production_core",
    "work_order_pay_detail": "standard_execution",
    "work_order_material": "production_core",
    "work_order_batch": "production_core",
    "production_movement": "production_core",
    "production_operation_undo": "production_core",
    "production_plan": "planning",
    "production_plan_item": "planning",
    "production_route_task": "planning",
    "inventory_stock": "inventory",
    "inventory_reservation": "inventory",
    "inventory_receipt": "inventory",
    "inventory_transaction": "inventory",
    "finished_order_stock": "inventory",
    "finished_goods_transaction": "inventory",
}


def table_owner(table_name: str) -> str:
    try:
        return TABLE_OWNERS[table_name]
    except KeyError as exc:
        raise LookupError(f"Table has no module owner: {table_name}") from exc
