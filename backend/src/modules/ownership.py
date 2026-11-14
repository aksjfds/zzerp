"""Authoritative table ownership for the modular monolith."""

TABLE_OWNERS = {
    "users": "identity",
    "user_sessions": "identity",
    "customer": "sales",
    "product": "engineering",
    "product_version": "engineering",
    "product_bom": "engineering",
    "product_process_flow": "engineering",
    "production_department": "organization",
    "product_department_route": "engineering",
    "product_route_component": "engineering",
    "department_work_order": "planning",
    "department_work_order_movement": "planning",
    "department_handoff_ticket": "planning",
    "department_movement_receipt_link": "planning",
    "production_plan": "planning",
    "production_plan_item": "planning",
}


def table_owner(table_name: str) -> str:
    try:
        return TABLE_OWNERS[table_name]
    except KeyError as exc:
        raise LookupError(f"Table has no module owner: {table_name}") from exc
