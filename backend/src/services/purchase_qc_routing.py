from models.organization import Procedure
from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from services.errors import DomainError
from services.procedure_tags import restore_tag_source
from services.work_order_support import move_to_node


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
) -> tuple[str | None, int | None]:
    target = context.normal_target(node["id"])
    target_department_id = move_to_node(
        session,
        production_item,
        target,
        quantity,
        node["id"],
    )
    return target.get("id") if target else None, target_department_id


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
