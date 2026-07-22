from sqlalchemy import select

from models.organization import Department, Procedure
from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from services.procedure_tags import (
    is_final_tag_set,
    procedure_department_id,
    route_tag_output,
)
from services.production_flow import process_qc_node
from services.errors import DomainError
from services.tag_work_order_rules import validate_tag_order_snapshot


def validate_context(session, order: WorkOrder, procedure: Procedure) -> None:
    validate_tag_order_snapshot(
        session,
        order,
        procedure,
        order.source_tag_set_id,
    )


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
    if qc_node is None:
        raise DomainError("work_order_qc_not_configured", "标记工艺后必须配置QC节点")
    if is_final_tag_set(
        session,
        production_item,
        procedure.id,
        order.target_tag_set_id,
    ):
        qc_department_id = session.scalar(
            select(Department.id).where(Department.department_code == "qc")
        )
        if qc_department_id is None:
            raise DomainError("department_not_found", "QC部门不存在")
        return qc_node["id"], qc_department_id
    route_tag_output(
        session,
        production_item=production_item,
        flow_node_id=node["id"],
        source_flow_node_id=batch.source_flow_node_id,
        procedure=procedure,
        target_tag_set_id=order.target_tag_set_id,
        quantity=quantity,
    )
    return node["id"], procedure_department_id(session, procedure)


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
    return procedure_department_id(session, procedure)
