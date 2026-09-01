from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from domain.production_types import STANDARD_EXECUTION_WORK_ORDER_TYPES
from modules.engineering.model_api import ProductBom
from modules.organization.model_api import Department, Workshop
from modules.production_core.persistence import (
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderMaterial,
)
from modules.sales.model_api import CustomerOrderItem
from modules.errors import DomainError
from modules.production_core.flow import (
    ProductionFlowContext,
    load_product_flow,
    load_production_flow,
    process_qc_node,
)


@dataclass(frozen=True, slots=True)
class WorkOrderSubmissionCapabilities:
    qc_available: bool
    direct_result_allowed: bool


def work_order_submission_capabilities(
    order: WorkOrder,
    flow: dict,
    nodes: dict[str, dict],
) -> WorkOrderSubmissionCapabilities:
    standard_execution = (
        order.work_order_type in STANDARD_EXECUTION_WORK_ORDER_TYPES
    )
    return WorkOrderSubmissionCapabilities(
        qc_available=(
            standard_execution
            and process_qc_node(flow, nodes, order.flow_node_id) is not None
        ),
        direct_result_allowed=standard_execution,
    )


def flow_context(session, production_item: ProductionItem) -> ProductionFlowContext:
    return load_production_flow(session, production_item)


def node_context(
    session,
    production_item: ProductionItem,
    node_id: str,
) -> tuple[ProductionFlowContext, dict]:
    context = flow_context(session, production_item)
    return context, context.node(node_id)


def production_item_unit_quantity(
    session,
    production_item: ProductionItem,
    bom_item: ProductBom | None,
) -> int:
    if bom_item is not None:
        return bom_item.pcs
    context = flow_context(session, production_item)
    origin = context.nodes.get(production_item.origin_flow_node_id, {})
    return int(origin.get("output_pcs", 1))


def target_department_id(session, node: dict) -> int:
    node_type = node.get("type")
    if node_type == "process":
        workshop = session.get(Workshop, node.get("workshop_id"))
        if workshop is None:
            raise DomainError("workshop_department_missing", "目标节点没有有效车间")
        return workshop.department_id
    if node_type == "finished_inbound":
        department_code = "finished"
    elif node_type == "assembly":
        workshop = session.get(Workshop, node.get("workshop_id"))
        if workshop is None:
            raise DomainError("workshop_department_missing", "目标节点没有有效车间")
        return workshop.department_id
    else:
        raise DomainError("flow_target_invalid", "目标节点类型不支持生产流转")
    department_id = session.scalar(
        select(Department.id).where(Department.department_code == department_code)
    )
    if department_id is None:
        raise DomainError("department_not_found", "目标部门不存在")
    return department_id


def move_to_node(
    session,
    production_item: ProductionItem,
    node: dict | None,
    quantity: int,
    source_node_id: str,
    source_work_order_id: int | None = None,
) -> int | None:
    if quantity <= 0 or node is None:
        return None
    session.get(ProductionItem, production_item.id, with_for_update=True)
    department_id = target_department_id(session, node)
    if node.get("type") == "finished_inbound":
        return department_id
    target = session.scalar(
        select(Repository)
        .where(
            Repository.production_item_id == production_item.id,
            Repository.flow_node_id == node["id"],
            Repository.source_flow_node_id == source_node_id,
            Repository.department_id == department_id,
            Repository.source_work_order_id == source_work_order_id,
        )
        .with_for_update()
    )
    if target is None:
        session.add(
            Repository(
                production_item_id=production_item.id,
                flow_node_id=node["id"],
                source_flow_node_id=source_node_id,
                department_id=department_id,
                source_work_order_id=source_work_order_id,
                quantity=quantity,
            )
        )
    else:
        target.quantity += quantity
    return department_id


def consume_repository(session, repository: Repository, quantity: int) -> None:
    remaining_quantity = repository.quantity - quantity
    if remaining_quantity < 0:
        raise DomainError("repository_quantity_insufficient", "当前库存数量不足")
    if remaining_quantity == 0:
        referenced_by_order = session.scalar(
            select(WorkOrder.id)
            .where(WorkOrder.repository_id == repository.id)
            .limit(1)
        )
        referenced_by_material = session.scalar(
            select(WorkOrderMaterial.id)
            .where(WorkOrderMaterial.repository_id == repository.id)
            .limit(1)
        )
        if referenced_by_order is not None or referenced_by_material is not None:
            raise DomainError(
                "repository_reference_invariant",
                "仓位仍被未消费的工单或装配物料引用，不能耗尽",
                status_code=409,
            )
        session.delete(repository)
    else:
        repository.quantity = remaining_quantity


def terminal_unit_quantity(session, flow: dict, nodes: dict[str, dict], node_id: str) -> int | None:
    incoming = {
        edge.get("source_node_id")
        for edge in flow.get("edges", [])
        if edge.get("target_node_id") == node_id
    }
    incoming.discard(None)
    if len(incoming) != 1:
        return None
    source_id = next(iter(incoming))
    source = nodes.get(source_id)
    if source is None:
        return None
    source_type = source.get("type")
    if source_type == "assembly":
        return int(source.get("output_pcs", 1))
    if source_type == "part":
        bom = session.get(ProductBom, source.get("bom_item_id"))
        return bom.pcs if bom is not None else None
    if source_type in {"process", "qc", "supplier_processing"}:
        return terminal_unit_quantity(session, flow, nodes, source_id)
    return None


def finished_inbound_node_and_unit_quantity(
    session,
    flow: dict,
    nodes: dict[str, dict],
) -> tuple[dict, int]:
    inbound_nodes = [
        node for node in nodes.values()
        if node.get("type") == "finished_inbound"
    ]
    if len(inbound_nodes) != 1:
        raise DomainError(
            "production_finished_inbound_node_invalid",
            "产品版本必须配置唯一的入库节点",
            status_code=409,
        )
    inbound_node = inbound_nodes[0]
    unit_quantity = terminal_unit_quantity(
        session,
        flow,
        nodes,
        inbound_node["id"],
    )
    if unit_quantity is None or unit_quantity <= 0:
        raise DomainError(
            "production_finished_inbound_unit_invalid",
            "产品版本无法确定有效的成品换算单位",
            status_code=409,
        )
    return inbound_node, unit_quantity
