from models.organization import Procedure
from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from services.procedure_tags import procedure_department_id, route_tag_output
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
