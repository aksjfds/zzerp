"""Inventory component identity rules exposed to collaborators."""


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


__all__ = ["component_identity_key"]
