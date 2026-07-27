from modules.errors import DomainError
from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import (
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.operational_api import process_qc_node
from modules.quality.context_api import InspectionBatchContext
from modules.standard_execution.tag_api import restore_tag_source


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
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
    if qc_node is None or qc_department_id is None:
        raise DomainError("work_order_qc_not_configured", "当前工艺后未配置有效QC节点")
    return qc_node["id"], qc_department_id


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
    return restore_tag_source(
        session,
        production_item=production_item,
        flow_node_id=node["id"],
        source_flow_node_id=batch.source_flow_node_id,
        procedure=procedure,
        source_tag_set_id=order.source_tag_set_id,
        quantity=quantity,
    )
