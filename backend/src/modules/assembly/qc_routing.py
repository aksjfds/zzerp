from modules.errors import DomainError
from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import (
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.operational_api import process_qc_node
from modules.quality.context_api import InspectionBatchContext


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
) -> tuple[str, int]:
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
    if qc_node is None or qc_department_id is None:
        raise DomainError("work_order_qc_not_configured", "装配节点后未配置有效QC节点")
    return qc_node["id"], qc_department_id


def route_rework(
    session,
    *,
    order: WorkOrderContext,
    batch: InspectionBatchContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext | None,
    node: dict,
    quantity: int,
) -> int:
    assembly_department_id = get_department_ids_by_codes(
        session,
        {"assembly"},
    ).get("assembly")
    if assembly_department_id is None:
        raise DomainError("department_not_found", "装配部不存在")
    return assembly_department_id
