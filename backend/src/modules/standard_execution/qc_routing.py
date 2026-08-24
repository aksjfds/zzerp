from modules.errors import DomainError
from modules.inventory.finished_goods_api import register_pending_finished_goods
from modules.organization.context_api import ProcedureContext
from modules.production_core.context_api import (
    InspectionBatchContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.operational_api import move_to_node, process_qc_node
from modules.production_core.ownership_api import add_repository_quantity
from modules.quality.routing_contract import QualifiedRouteResult, ReworkRouteResult
from modules.standard_execution.procedure_api import procedure_department_id


def validate_context(
    session,
    order: WorkOrderContext,
    procedure: ProcedureContext | None,
) -> None:
    if procedure is None or order.procedure_id != procedure.id:
        raise DomainError("work_order_context_invalid", "工单工艺资料不一致")


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
    qualified_disposition: str | None,
) -> QualifiedRouteResult:
    if procedure is None:
        raise DomainError("work_order_context_invalid", "工单工艺资料不一致")
    if qualified_disposition == "return":
        department_id = procedure_department_id(session, procedure)
        add_repository_quantity(
            session,
            production_item_id=production_item.id,
            flow_node_id=node["id"],
            source_flow_node_id=node["id"],
            department_id=department_id,
            quantity=quantity,
            source_work_order_id=order.id,
        )
        return QualifiedRouteResult(node["id"], department_id)
    if qualified_disposition != "release":
        raise DomainError("qc_disposition_required", "请选择合格品返回当前车间或放行下一节点")
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    if qc_node is None:
        raise DomainError("work_order_qc_not_configured", "当前车间节点后未配置QC节点")
    target = context.normal_target(qc_node["id"])
    if target is None:
        raise DomainError("qc_target_missing", "QC节点没有后续流程节点")
    department_id = move_to_node(
        session,
        production_item,
        target,
        quantity,
        qc_node["id"],
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
    if procedure is None:
        raise DomainError("work_order_context_invalid", "工单工艺资料不一致")
    return ReworkRouteResult(procedure_department_id(session, procedure))
