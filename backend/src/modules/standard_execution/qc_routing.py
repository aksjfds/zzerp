from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import (
    ProductionItemContext,
    WorkOrderContext,
)
from modules.quality.context_api import InspectionBatchContext
from modules.standard_execution.tags import (
    is_final_tag_set,
    procedure_department_id,
    route_tag_output,
)
from modules.production_core.operational_api import process_qc_node
from modules.errors import DomainError
from modules.standard_execution.rules import validate_tag_order_snapshot


def validate_context(
    session,
    order: WorkOrderContext,
    procedure: ProcedureContext,
) -> None:
    validate_tag_order_snapshot(
        session,
        order,
        procedure,
        order.source_tag_set_id,
    )


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
    final_tag_set = is_final_tag_set(
        session,
        production_item,
        procedure.id,
        order.target_tag_set_id,
    )
    if final_tag_set:
        if qc_node is None:
            raise DomainError(
                "work_order_qc_not_configured",
                "全部标记已完成且当前工艺未配置QC节点",
            )
        qc_department_id = get_department_ids_by_codes(
            session,
            {"qc"},
        ).get("qc")
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
    order: WorkOrderContext,
    batch: InspectionBatchContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext,
    node: dict,
    quantity: int,
) -> int:
    return procedure_department_id(session, procedure)
