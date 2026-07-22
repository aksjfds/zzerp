from sqlalchemy import select

from models.organization import Department, Procedure
from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from services.errors import DomainError
from services.production_flow import process_qc_node


def validate_context(session, order: WorkOrder, procedure: Procedure | None) -> None:
    if order.work_order_type != "assembly" or order.procedure_id is not None:
        raise DomainError("work_order_type_invalid", "装配送检工单资料无效")


def route_qualified(
    session,
    *,
    order: WorkOrder,
    batch: WorkOrderBatch,
    production_item: ProductionItem,
    procedure: Procedure | None,
    context,
    node: dict,
    quantity: int,
) -> tuple[str, int]:
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    qc_department_id = session.scalar(
        select(Department.id).where(Department.department_code == "qc")
    )
    if qc_node is None or qc_department_id is None:
        raise DomainError("work_order_qc_not_configured", "装配节点后未配置有效QC节点")
    return qc_node["id"], qc_department_id


def route_rework(
    session,
    *,
    order: WorkOrder,
    batch: WorkOrderBatch,
    production_item: ProductionItem,
    procedure: Procedure | None,
    node: dict,
    quantity: int,
) -> int:
    assembly_department_id = session.scalar(
        select(Department.id).where(Department.department_code == "assembly")
    )
    if assembly_department_id is None:
        raise DomainError("department_not_found", "装配部门不存在")
    return assembly_department_id
