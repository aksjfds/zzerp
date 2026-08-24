"""Stable material identity shared by planning and execution modules."""


def production_item_material_key(production_item) -> str:
    if production_item.product_bom_id is not None:
        return f"part:{production_item.product_bom_id}"
    return f"assembly:{production_item.origin_flow_node_id}"


__all__ = ["production_item_material_key"]
