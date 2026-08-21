from modules.errors import DomainError
from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import (
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.operational_api import move_to_node, process_qc_node
from modules.production_core.ownership_api import add_repository_quantity
from modules.quality.context_api import InspectionBatchContext
from modules.standard_execution.procedures import procedure_department_id


def validate_context(
    session,
    order: WorkOrderContext,
    procedure: ProcedureContext,
) -> None:
    if procedure.procedure_type != "purchase_receipt":
        raise DomainError("work_order_type_invalid", "外购入库工单所属工艺无效")


def route_qualified(
    session,
    *,
    order: WorkOrderContext,
    batch: InspectionBatchContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext,
    context,
    node: dict,
    quantity: int,
) -> tuple[str, int]:
    if batch.qualified_disposition == "return":
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
        return node["id"], department_id
    if batch.qualified_disposition != "release":
        raise DomainError("qc_disposition_required", "请选择合格品返回当前车间或放行下一节点")
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    if qc_node is None:
        raise DomainError("work_order_qc_not_configured", "当前工艺后未配置有效QC节点")
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
    return target["id"], department_id


def route_rework(
    session,
    *,
    order: WorkOrderContext,
    batch: InspectionBatchContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext,
    node: dict,
    quantity: int,
) -> int:
    return procedure_department_id(session, procedure)
