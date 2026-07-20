from sqlalchemy import select

from database import SessionLocal
from domain.time import utc_now
from models.organization import Department, Procedure
from models.production import (
    ProductionItem,
    WorkOrder,
    WorkOrderBatch,
)
from services.errors import DomainError
from services.procedure_tags import (
    ensure_tag_price_configs,
    get_or_create_tag,
    get_or_create_tag_set,
    procedure_department_id,
    route_tag_output,
    target_tag_set,
)
from services.production_movements import record_movement
from services.work_order_command_support import (
    InventorySource,
    consume_order_source,
    create_order_record,
    load_order_source,
)
from services.work_order_presenters import serialize_batch, serialize_work_order
from services.work_order_progress import (
    calculate_work_order_progress,
    order_remaining_quantity,
    rework_pending_quantities,
)
from services.work_order_support import node_context, refresh_order_closed
from services.tag_work_order_rules import (
    normalize_tag_names,
    validate_tag_order,
    validate_tag_order_snapshot,
    validate_tag_source,
)


def create_tag_order(
    session,
    *,
    source: InventorySource,
    production_item: ProductionItem,
    procedure: Procedure,
    tag_names: list[str],
    quantity: int,
    worker_id: int | None,
) -> WorkOrder:
    source_tag_set_id = validate_tag_source(session, source, procedure)
    normalized_tag_names = normalize_tag_names(tag_names)
    applied_tags = [
        get_or_create_tag(session, procedure, tag_name)
        for tag_name in normalized_tag_names
    ]
    ensure_tag_price_configs(
        session,
        production_item.product_bom_id,
        procedure,
        applied_tags,
    )
    applied_set = get_or_create_tag_set(
        session,
        procedure,
        [tag.id for tag in applied_tags],
    )
    target_set = target_tag_set(
        session,
        procedure,
        source_tag_set_id,
        applied_tags,
    )
    return create_order_record(
        session,
        source=source,
        production_item=production_item,
        procedure=procedure,
        quantity=quantity,
        worker_id=worker_id,
        work_order_type="tag",
        applied_tag_set_id=applied_set.id,
        applied_tag_names=[tag.tag_name for tag in applied_tags],
        source_tag_set_id=source_tag_set_id,
        target_tag_set_id=target_set.id,
    )


def submit_tag_order(
    session,
    *,
    order: WorkOrder,
    source: InventorySource,
    production_item: ProductionItem,
    procedure: Procedure,
    node: dict,
    quantity: int,
    completion_action: str,
) -> dict:
    validate_tag_order(session, order, source, procedure)
    if completion_action != "qc":
        raise DomainError(
            "tag_work_order_complete_required",
            "标准生产工单请使用完成按钮结单",
        )
    remaining = order_remaining_quantity(order)
    if quantity <= 0 or quantity > remaining or quantity > source.quantity:
        raise DomainError("submission_quantity_exceeded", "提交数量超过工单剩余数量")
    batch = WorkOrderBatch(
        work_order_id=order.id,
        submitted_quantity=quantity,
        source_flow_node_id=order.source_flow_node_id,
    )
    session.add(batch)
    session.flush()
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type="process",
        source_flow_node_id=node["id"],
        target_flow_node_id=None,
        source_tag_set_id=order.source_tag_set_id,
        target_tag_set_id=order.target_tag_set_id,
        source_department_id=source.department_id,
        target_department_id=None,
        work_order_id=order.id,
        work_order_batch_id=batch.id,
    )
    session.flush()
    order.completed_quantity += quantity
    consume_order_source(session, order, source, quantity)
    session.flush()
    refresh_order_closed(session, production_item)
    return serialize_work_order(session, order)


def complete_tag_work_order(work_order_id: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.work_order_type != "tag":
            raise DomainError("work_order_complete_type_invalid", "当前工单不使用生产结单流程")
        if order.status != "open":
            raise DomainError("work_order_closed", "工单已经结单")

        production_item = session.get(
            ProductionItem,
            order.production_item_id,
            with_for_update=True,
        )
        if production_item is None:
            raise DomainError("production_context_missing", "生产项不存在")
        _, node = node_context(session, production_item, order.flow_node_id)
        procedure = session.get(Procedure, node.get("procedure_id"))
        if procedure is None or order.procedure_id != procedure.id:
            raise DomainError("procedure_not_found", "工单所属工艺不存在")
        department_id = procedure_department_id(session, procedure)
        department = session.get(Department, department_id)
        if department is None or user_department not in {
            "sys",
            department.department_code,
        }:
            raise DomainError("department_access_denied", "无权完成该工单", status_code=403)
        validate_tag_order_snapshot(
            session,
            order,
            procedure,
            order.source_tag_set_id,
        )

        batches = list(
            session.scalars(
                select(WorkOrderBatch).where(WorkOrderBatch.work_order_id == order.id)
            ).all()
        )
        progress = calculate_work_order_progress(order, batches)
        if progress.pending_qc_quantity:
            raise DomainError("work_order_qc_pending", "仍有待检批次，不能结单")
        if progress.rework_pending_quantity:
            raise DomainError("work_order_rework_pending", "仍有返工数量未重新送检，不能结单")

        remaining = progress.initial_processing_quantity
        if remaining and bool(node.get("qc_required", False)):
            raise DomainError("work_order_qc_required", "仍有未送检数量，不能结单")
        if remaining:
            source, _ = load_order_source(session, order)
            if (
                order.source_flow_node_id is None
                or source.source_flow_node_id != order.source_flow_node_id
            ):
                raise DomainError(
                    "work_order_source_snapshot_invalid",
                    "工单来源快照与当前库存位置不一致",
                )
            if source.department_id != department_id:
                raise DomainError("work_order_source_department_invalid", "工单来源部门无效")
            validate_tag_order(session, order, source, procedure)
            if source.quantity < remaining:
                raise DomainError("submission_quantity_exceeded", "工单来源数量不足")
            route_tag_output(
                session,
                production_item=production_item,
                flow_node_id=node["id"],
                source_flow_node_id=order.source_flow_node_id,
                procedure=procedure,
                target_tag_set_id=order.target_tag_set_id,
                quantity=remaining,
            )
            record_movement(
                session,
                production_item=production_item,
                quantity=remaining,
                movement_type="process",
                source_flow_node_id=node["id"],
                target_flow_node_id=node["id"],
                source_tag_set_id=order.source_tag_set_id,
                target_tag_set_id=order.target_tag_set_id,
                source_department_id=department_id,
                target_department_id=department_id,
                work_order_id=order.id,
            )
            order.completed_quantity += remaining
            consume_order_source(session, order, source, remaining)

        order.status = "closed"
        order.closed_at = utc_now()
        session.flush()
        refresh_order_closed(session, production_item)
        return serialize_work_order(session, order)


def resubmit_tag_rework_batch(
    source_batch_id: int,
    quantity: int,
    user_department: str,
) -> dict:
    with SessionLocal.begin() as session:
        source_batch = session.get(
            WorkOrderBatch,
            source_batch_id,
            with_for_update=True,
        )
        if source_batch is None:
            raise DomainError("qc_batch_not_found", "返工来源批次不存在", status_code=404)
        order = session.get(WorkOrder, source_batch.work_order_id, with_for_update=True)
        if order is None or order.work_order_type != "tag":
            raise DomainError("qc_rework_order_invalid", "返工批次所属工单无效")
        if order.status != "open":
            raise DomainError("work_order_closed", "工单已经结单")
        if source_batch.recorded_at is None or source_batch.rework_quantity is None:
            raise DomainError("qc_batch_not_completed", "QC 尚未录入返工结果")

        order_batches = list(
            session.scalars(
                select(WorkOrderBatch).where(WorkOrderBatch.work_order_id == order.id)
            ).all()
        )
        available = rework_pending_quantities(order_batches).get(source_batch.id, 0)
        if quantity <= 0 or quantity > available:
            raise DomainError("qc_rework_quantity_exceeded", "返工送检数量超过待返工数量")

        production_item = session.get(ProductionItem, order.production_item_id)
        if production_item is None:
            raise DomainError("production_context_missing", "生产项不存在")
        _, node = node_context(session, production_item, order.flow_node_id)
        procedure = session.get(Procedure, node.get("procedure_id"))
        if procedure is None or order.procedure_id != procedure.id:
            raise DomainError("procedure_not_found", "工单所属工艺不存在")
        department_id = procedure_department_id(session, procedure)
        department = session.get(Department, department_id)
        if department is None or user_department not in {
            "sys",
            department.department_code,
        }:
            raise DomainError("department_access_denied", "无权提交返工送检", status_code=403)
        validate_tag_order_snapshot(
            session,
            order,
            procedure,
            order.source_tag_set_id,
        )

        batch = WorkOrderBatch(
            work_order_id=order.id,
            submitted_quantity=quantity,
            source_flow_node_id=source_batch.source_flow_node_id,
            rework_source_batch_id=source_batch.id,
        )
        session.add(batch)
        session.flush()
        record_movement(
            session,
            production_item=production_item,
            quantity=quantity,
            movement_type="process",
            source_flow_node_id=node["id"],
            target_flow_node_id=None,
            source_tag_set_id=order.source_tag_set_id,
            target_tag_set_id=order.target_tag_set_id,
            source_department_id=department_id,
            target_department_id=None,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        session.flush()
        return serialize_batch(batch, track_rework=True)
