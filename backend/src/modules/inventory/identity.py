def component_identity_key(
    *,
    department_code: str,
    item_type: str,
    product_id: int,
    product_version: int,
    product_bom_id: int | None,
    flow_node_id: str,
) -> str:
    bom_key = str(product_bom_id) if product_bom_id is not None else "-"
    return ":".join((
        department_code,
        item_type,
        str(product_id),
        str(product_version),
        bom_key,
        flow_node_id,
    ))


def inventory_identity_key(
    *,
    department_code: str,
    item_type: str,
    product_id: int,
    product_version: int,
    product_bom_id: int | None,
    flow_node_id: str,
    completed_flow_node_id: str,
) -> str:
    """Identify one component and its last fully completed flow node."""
    return ":".join((
        component_identity_key(
            department_code=department_code,
            item_type=item_type,
            product_id=product_id,
            product_version=product_version,
            product_bom_id=product_bom_id,
            flow_node_id=flow_node_id,
        ),
        completed_flow_node_id,
    ))


__all__ = ["component_identity_key", "inventory_identity_key"]
