from __future__ import annotations

"""Production-plan inventory reservation orchestration."""

from math import ceil
from sqlalchemy import select
from sqlalchemy.orm import Session
from modules.errors import DomainError
from modules.engineering.model_api import ProductProcessFlow
from modules.planning.execution_contract import PlanExecutionCollaborators
from modules.planning.persistence import ProductionPlan, ProductionPlanItem

def _reserve_and_validate_plan_item(
    session: Session,
    plan: ProductionPlan,
    item: ProductionPlanItem,
    actor_username: str,
    collaborators: PlanExecutionCollaborators,
) -> None:
    allocated = collaborators.reserve_plan_item(
        session,
        production_plan_id=plan.id,
        production_plan_item_id=item.id,
        plan_item=item,
        requested_quantity=item.gross_required_quantity,
        actor_username=actor_username,
    )
    item.reserved_inventory_quantity = allocated
    item.estimated_inventory_quantity = allocated
    item.net_required_quantity = item.gross_required_quantity - allocated
    if item.planned_production_quantity < item.net_required_quantity:
        raise DomainError(
            "production_plan_inventory_changed",
            f"{item.item_code} {item.item_name}的可用库存已变化，请重新加载并填写生产数量",
            status_code=409,
            path="items",
        )

def _reserve_flow_items(
    session: Session,
    plan: ProductionPlan,
    items: list[ProductionPlanItem],
    shipping_node_id: str,
    required_product_quantity: int,
    actor_username: str,
    collaborators: PlanExecutionCollaborators,
) -> None:
    sample = items[0]
    flow_record = session.scalar(select(ProductProcessFlow).where(
        ProductProcessFlow.product_id == sample.product_id,
        ProductProcessFlow.product_version == sample.product_version,
    ))
    if flow_record is None:
        raise DomainError("product_engineering_data_missing", "产品版本缺少流程图")
    flow = flow_record.flow_json
    nodes = {node.get("id"): node for node in flow.get("nodes", [])}
    incoming: dict[str, list[str]] = {}
    for edge in flow.get("edges", []):
        incoming.setdefault(edge.get("target_node_id"), []).append(edge.get("source_node_id"))
    by_node = {item.flow_node_id: item for item in items}

    def visit(node_id: str, required_units: int, visiting: set[str]) -> None:
        if node_id in visiting:
            raise DomainError("product_flow_cycle", "产品流程图不能形成循环")
        node = nodes.get(node_id)
        if node is None:
            return
        next_required = required_units
        if node.get("type") in {"assembly", "part"}:
            item = by_node.get(node_id)
            if item is None:
                raise DomainError("production_plan_flow_mismatch", "生产计划与流程图不一致")
            item.gross_required_quantity = required_units * item.unit_requirement
            if node.get("type") in {"assembly", "part"}:
                _reserve_and_validate_plan_item(
                    session, plan, item, actor_username, collaborators
                )
            if node.get("type") == "assembly":
                next_required = ceil(item.net_required_quantity / item.unit_requirement)
        for source_id in incoming.get(node_id, []):
            if source_id:
                visit(source_id, next_required, visiting | {node_id})

    visit(shipping_node_id, required_product_quantity, set())
