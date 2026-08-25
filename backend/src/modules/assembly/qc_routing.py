from domain.production_types import QcQualifiedDestination
from modules.errors import DomainError
from modules.inventory.finished_goods_api import register_pending_finished_goods
from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import (
    InspectionBatchContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.flow_api import process_qc_node, qc_release_target
from modules.production_core.operational_api import move_to_node
from modules.production_core.ownership_api import add_repository_quantity
from modules.quality.routing_api import QualifiedRouteResult, ReworkRouteResult


def validate_context(
    session,
    order: WorkOrderContext,
    procedure: ProcedureContext | None,
) -> None:
    if (
        order.work_order_type != "assembly"
        or order.procedure_id != (procedure.id if procedure else None)
    ):
        raise DomainError("work_order_type_invalid", "装配送检工单资料无效")


def route_qualified(
    session,
    *,
    order: WorkOrderContext,
    batch: InspectionBatchContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext | None,
    context,
    node: dict,
    quantity: int,
    destination: QcQualifiedDestination,
) -> QualifiedRouteResult:
    assembly_department_id = get_department_ids_by_codes(session, {"assembly"}).get("assembly")
    if destination == "return":
        if assembly_department_id is None:
            raise DomainError("department_not_found", "装配部不存在")
        add_repository_quantity(
            session,
            production_item_id=production_item.id,
            flow_node_id=node["id"],
            source_flow_node_id=node["id"],
            department_id=assembly_department_id,
            quantity=quantity,
            source_work_order_id=order.id,
        )
        return QualifiedRouteResult(node["id"], assembly_department_id)
    if destination != "release":
        raise DomainError("qc_disposition_required", "请选择合格品返回当前车间或放行下一节点")
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    target = qc_release_target(context.flow, context.nodes, node["id"])
    if target is None:
        raise DomainError("qc_target_missing", "当前装配节点没有可放行的后续流程节点")
    department_id = move_to_node(
        session,
        production_item,
        target,
        quantity,
        qc_node["id"] if qc_node is not None else node["id"],
        source_work_order_id=order.id,
    )
    if department_id is None:
        raise DomainError("qc_target_missing", "QC节点没有后续流程节点")
    if target.get("type") == "shipping":
        register_pending_finished_goods(
            session,
            production_item=production_item,
            shipping_node_id=target["id"],
            quantity=quantity,
        )
    return QualifiedRouteResult(target["id"], department_id)


def route_rework(
    session,
    *,
    order: WorkOrderContext,
    batch: InspectionBatchContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext | None,
    node: dict,
    quantity: int,
) -> ReworkRouteResult:
    assembly_department_id = get_department_ids_by_codes(
        session,
        {"assembly"},
    ).get("assembly")
    if assembly_department_id is None:
        raise DomainError("department_not_found", "装配部不存在")
    return ReworkRouteResult(assembly_department_id)
