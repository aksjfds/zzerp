from sqlalchemy import select

from database import SessionLocal
from models.organization import Department, Procedure
from models.production import (
    ProductionItem,
    WorkOrder,
    WorkOrderBatch,
)
from services.errors import DomainError
from services.procedure_tags import (
    configured_tag_suggestions,
    get_or_create_tag_set,
    procedure_department_id,
    tag_set_tags,
    target_tag_set,
)
from services.production_movements import record_movement
from services.work_order_command_support import (
    InventorySource,
    consume_order_source,
    create_order_record,
)
from services.work_order_presenters import serialize_batch, serialize_work_order
from services.work_order_progress import order_remaining_quantity, rework_pending_quantities
from services.work_order_support import node_context, refresh_order_closed
from services.production_flow import process_qc_node
from services.production_operation_undo import (
    capture_operation_state,
    record_undoable_operation,
)
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
    configured_tags = configured_tag_suggestions(
        session,
        production_item,
        procedure.id,
    )
    configured_by_name = {tag.tag_name: tag for tag in configured_tags}
    if not configured_by_name:
        raise DomainError("procedure_tags_not_configured", "请先配置该配件的必做标记")
    unknown_names = [name for name in normalized_tag_names if name not in configured_by_name]
    if unknown_names:
        raise DomainError("procedure_tag_not_configured", "工单只能使用该配件已配置的标记")
    applied_tags = [configured_by_name[name] for name in normalized_tag_names]
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
    target_ids = {tag.id for tag in tag_set_tags(session, target_set.id)}
    configured_ids = {tag.id for tag in configured_tags}
    if not target_ids <= configured_ids:
        raise DomainError("procedure_tag_set_not_configured", "目标标记组合超出配件配置")
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
            "tag_work_order_qc_required",
            "打完标记后必须送检",
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
    context, _ = node_context(session, production_item, node["id"])
    qc_node = process_qc_node(context.flow, context.nodes, node["id"])
    if qc_node is None:
        raise DomainError("work_order_qc_not_configured", "标记工艺后必须配置QC节点")
    qc_department = session.scalar(
        select(Department).where(Department.department_code == "qc")
    )
    if qc_department is None:
        raise DomainError("department_not_found", "QC部门不存在")
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type="process",
        source_flow_node_id=node["id"],
        target_flow_node_id=qc_node["id"],
        source_tag_set_id=order.source_tag_set_id,
        target_tag_set_id=order.target_tag_set_id,
        source_department_id=source.department_id,
        target_department_id=qc_department.id,
        work_order_id=order.id,
        work_order_batch_id=batch.id,
    )
    session.flush()
    order.completed_quantity += quantity
    consume_order_source(session, order, source, quantity)
    session.flush()
    refresh_order_closed(session, production_item)
    return serialize_work_order(session, order)


def resubmit_tag_rework_batch(
    source_batch_id: int,
    quantity: int,
    user_department: str,
    actor_username: str,
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
        before = capture_operation_state(session, order)
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
        context, node = node_context(session, production_item, order.flow_node_id)
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
        qc_node = process_qc_node(context.flow, context.nodes, node["id"])
        if qc_node is None:
            raise DomainError("work_order_qc_not_configured", "标记工艺后必须配置QC节点")
        qc_department = session.scalar(
            select(Department).where(Department.department_code == "qc")
        )
        if qc_department is None:
            raise DomainError("department_not_found", "QC部门不存在")

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
            target_flow_node_id=qc_node["id"],
            source_tag_set_id=order.source_tag_set_id,
            target_tag_set_id=order.target_tag_set_id,
            source_department_id=department_id,
            target_department_id=qc_department.id,
            work_order_id=order.id,
            work_order_batch_id=batch.id,
        )
        session.flush()
        record_undoable_operation(
            session,
            order,
            before,
            operation_type="rework_submission",
            operation_label="撤回返工送检",
            department_code=department.department_code,
            actor_username=actor_username,
        )
        return serialize_batch(batch, track_rework=True)
