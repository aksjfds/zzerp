"""Protect published flow identities referenced by department configuration."""

from sqlalchemy.orm import Session

from modules.errors import DomainError
from modules.engineering.collaboration_contract import EngineeringCollaborators


def ensure_priced_bom_items_retained(
    session: Session,
    *,
    product_id: int,
    product_version: int,
    retained_bom_ids: set[int],
    collaborators: EngineeringCollaborators,
) -> None:
    referenced_bom_ids = {
        int(material_key.removeprefix("part:"))
        for material_key, _flow_node_id in collaborators.product_version_procedure_price_references(
            session,
            product_id,
            product_version,
        )
        if material_key.startswith("part:")
    }
    if referenced_bom_ids - retained_bom_ids:
        raise DomainError(
            "priced_bom_item_in_use",
            "BOM 配件已配置工艺与单价，不能删除；请先删除相关配置或创建新版本",
            status_code=409,
        )


def ensure_priced_flow_node_identities_preserved(
    session: Session,
    *,
    product_id: int,
    product_version: int,
    current_flow: dict,
    proposed_flow: dict,
    collaborators: EngineeringCollaborators,
) -> None:
    references = collaborators.product_version_procedure_price_references(
        session,
        product_id,
        product_version,
    )
    referenced_node_ids = {flow_node_id for _material_key, flow_node_id in references}
    referenced_node_ids.update(
        material_key.removeprefix("assembly:")
        for material_key, _flow_node_id in references
        if material_key.startswith("assembly:")
    )
    if not referenced_node_ids:
        return

    current_nodes = _nodes_by_id(current_flow)
    proposed_nodes = _nodes_by_id(proposed_flow)
    for node_id in referenced_node_ids:
        current = current_nodes.get(node_id)
        proposed = proposed_nodes.get(node_id)
        if (
            current is None
            or proposed is None
            or _identity_signature(current) != _identity_signature(proposed)
        ):
            raise DomainError(
                "priced_flow_node_in_use",
                "流程节点已配置工艺与单价，不能删除、换号或改变节点归属；请先删除相关配置或创建新版本",
                status_code=409,
                element_id=node_id,
            )


def _nodes_by_id(flow: dict) -> dict[str, dict]:
    return {
        str(node["id"]): node
        for node in flow.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }


def _identity_signature(node: dict) -> tuple[object, ...]:
    return (
        node.get("type"),
        node.get("workshop_id"),
        node.get("bom_item_id"),
    )


__all__ = [
    "ensure_priced_bom_items_retained",
    "ensure_priced_flow_node_identities_preserved",
]
