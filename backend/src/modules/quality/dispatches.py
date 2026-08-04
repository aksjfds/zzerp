from database import SessionLocal
from domain.production_types import (
    MOVEMENT_QC_DISPATCH,
    WORK_ORDER_ASSEMBLY,
    WORK_ORDER_PURCHASE_RECEIPT,
    WORK_ORDER_TAG,
)
from modules.errors import DomainError
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import WorkOrderContext
from modules.production_core.operational_api import (
    move_to_node,
    node_context,
    process_qc_node,
    record_movement,
    refresh_order_closed,
)
from modules.production_core.qc_api import (
    dispatched_qc_quantity,
    load_qc_production_item,
    load_qc_work_order,
)
from modules.quality.persistence import WorkOrderBatch
from modules.standard_execution.tag_api import is_final_tag_set


def qc_release_context(
    session,
    batch: WorkOrderBatch,
    order: WorkOrderContext,
    dispatched_quantity: int | None = None,
) -> dict | None:
    if batch.recorded_at is None or not batch.qualified_quantity:
        return None
    production_item = load_qc_production_item(session, order.production_item_id)
    if production_item is None:
        return None
    context, process_node = node_context(session, production_item, order.flow_node_id)
    qc_node = process_qc_node(context.flow, context.nodes, process_node["id"])
    if order.work_order_type == WORK_ORDER_TAG:
        if order.procedure_id is None or not is_final_tag_set(
            session,
            production_item,
            order.procedure_id,
            order.target_tag_set_id,
        ):
            return None
    elif order.work_order_type not in {
        WORK_ORDER_PURCHASE_RECEIPT,
        WORK_ORDER_ASSEMBLY,
    }:
        return None
    if qc_node is None:
        return None
    dispatched = dispatched_quantity
    if dispatched is None:
        dispatched = dispatched_qc_quantity(session, batch.id)
    target = context.normal_target(qc_node["id"])
    return {
        "production_item": production_item,
        "qc_node": qc_node,
        "target": target,
        "dispatchable_quantity": max(batch.qualified_quantity - int(dispatched), 0),
    }


def dispatch_qc_batch(
    batch_id: int,
    quantity: int,
    user_department: str,
) -> dict:
    if user_department not in {"sys", "qc"}:
        raise DomainError("qc_access_denied", "只有QC可以放行合格数量", status_code=403)
    with SessionLocal.begin() as session:
        batch = session.get(WorkOrderBatch, batch_id, with_for_update=True)
        if batch is None:
            raise DomainError("qc_batch_not_found", "QC批次不存在", status_code=404)
        order = load_qc_work_order(
            session,
            batch.work_order_id,
            for_update=True,
        )
        if order is None:
            raise DomainError("work_order_not_found", "QC批次所属工单不存在", status_code=404)
        release = qc_release_context(session, batch, order)
        if release is None:
            raise DomainError("qc_batch_not_dispatchable", "当前批次不是可放行的最终工艺批次")
        if quantity <= 0 or quantity > release["dispatchable_quantity"]:
            raise DomainError("qc_dispatch_quantity_exceeded", "放行数量超过合格待放行数量")
        target = release["target"]
        if target is None:
            raise DomainError("qc_target_missing", "QC节点没有有效后续流程节点")
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_department_id is None:
            raise DomainError("department_not_found", "QC部门不存在")
        target_department_id = move_to_node(
            session,
            release["production_item"],
            target,
            quantity,
            release["qc_node"]["id"],
        )
        record_movement(
            session,
            production_item=release["production_item"],
            quantity=quantity,
            movement_type=MOVEMENT_QC_DISPATCH,
            source_flow_node_id=release["qc_node"]["id"],
            target_flow_node_id=target["id"],
            source_tag_set_id=order.target_tag_set_id,
            target_tag_set_id=None,
            source_department_id=qc_department_id,
            target_department_id=target_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        session.flush()
        refresh_order_closed(session, release["production_item"])
        return {
            "batch_id": batch.id,
            "quantity": quantity,
            "remaining_quantity": release["dispatchable_quantity"] - quantity,
            "target_flow_node_id": target["id"],
            "target_department_id": target_department_id,
        }
