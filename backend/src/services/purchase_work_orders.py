from sqlalchemy import select

from domain.time import utc_now
from models.organization import Department, Procedure
from models.production import ProductionItem, Repository, WorkOrder, WorkOrderBatch
from services.errors import DomainError
from services.production_movements import record_movement
from services.work_order_command_support import (
    InventorySource,
    consume_order_source,
    create_order_record,
)
from services.work_order_presenters import serialize_work_order
from services.work_order_progress import order_remaining_quantity
from services.work_order_support import move_to_node, refresh_order_closed
from services.production_flow import process_qc_node


def create_purchase_order(
    session,
    *,
    source: InventorySource,
    production_item: ProductionItem,
    procedure: Procedure,
    tag_names: list[str],
    quantity: int,
    worker_id: int | None,
    remark: str | None,
) -> WorkOrder:
    if not isinstance(source, Repository):
        raise DomainError("purchase_source_invalid", "外购入库单只能使用待外购数量")
    if any((tag_name or "").strip() for tag_name in tag_names):
        raise DomainError("purchase_tag_not_allowed", "外购入库工单不使用生产标记")
    return create_order_record(
        session,
        source=source,
        production_item=production_item,
        procedure=procedure,
        quantity=quantity,
        worker_id=worker_id,
        work_order_type="purchase_receipt",
        remark=remark,
    )


def submit_purchase_order(
    session,
    *,
    order: WorkOrder,
    source: InventorySource,
    production_item: ProductionItem,
    procedure: Procedure,
    context,
    node: dict,
    quantity: int,
    completion_action: str,
) -> dict:
    if procedure.procedure_type != "purchase_receipt":
        raise DomainError("work_order_type_invalid", "外购入库工单所属工艺无效")
    remaining = order_remaining_quantity(order)
    if quantity <= 0 or quantity > remaining or quantity > source.quantity:
        raise DomainError("submission_quantity_exceeded", "提交数量超过工单剩余数量")

    batch = None
    target_flow_node_id = None
    target_department_id = None
    if completion_action == "qc":
        qc_node = process_qc_node(context.flow, context.nodes, node["id"])
        qc_department_id = session.scalar(
            select(Department.id).where(Department.department_code == "qc")
        )
        if qc_node is None or qc_department_id is None:
            raise DomainError("work_order_qc_not_configured", "当前工艺后未配置有效QC节点")
        batch = WorkOrderBatch(
            work_order_id=order.id,
            submitted_quantity=quantity,
            source_flow_node_id=order.source_flow_node_id,
        )
        session.add(batch)
        session.flush()
        target_flow_node_id = qc_node["id"]
        target_department_id = qc_department_id
    else:
        target = context.normal_target(node["id"])
        target_department_id = move_to_node(
            session,
            production_item,
            target,
            quantity,
            node["id"],
        )
        target_flow_node_id = target.get("id") if target else None

    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type="purchase_receipt",
        source_flow_node_id=node["id"],
        target_flow_node_id=target_flow_node_id,
        source_tag_set_id=None,
        target_tag_set_id=None,
        source_department_id=source.department_id,
        target_department_id=target_department_id,
        work_order_id=order.id,
        work_order_batch_id=batch.id if batch else None,
    )
    session.flush()
    order.completed_quantity += quantity
    if quantity == remaining:
        order.status = "closed"
        order.closed_at = utc_now()
    consume_order_source(session, order, source, quantity)
    session.flush()
    refresh_order_closed(session, production_item)
    return serialize_work_order(session, order)
