from sqlalchemy import select

from models.organization import Department, Procedure
from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from services.errors import DomainError
from services.procedure_tags import restore_tag_source
from services.production_flow import process_qc_node


def validate_context(session, order: WorkOrder, procedure: Procedure) -> None:
    if procedure.procedure_type != "purchase_receipt":
        raise DomainError("work_order_type_invalid", "外购入库工单所属工艺无效")


def route_qualified(
    session,
    *,
    order: WorkOrder,
    batch: WorkOrderBatch,
    production_item: ProductionItem,
    procedure: Procedure,
    context,
    node: dict,
    quantity: int,
) -> tuple[str, int]:
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    qc_department_id = session.scalar(
        select(Department.id).where(Department.department_code == "qc")
    )
    if qc_node is None or qc_department_id is None:
        raise DomainError("work_order_qc_not_configured", "当前工艺后未配置有效QC节点")
    return qc_node["id"], qc_department_id


def route_rework(
    session,
    *,
    order: WorkOrder,
    batch: WorkOrderBatch,
    production_item: ProductionItem,
    procedure: Procedure,
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
