from sqlalchemy import func, select

from database import SessionLocal
from domain.time import business_now, utc_now
from models.organization import Department, Procedure, ProcedureTagSet, Worker
from models.production import (
    ProcedureTagStock,
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderBatch,
)
from services.assembly_work_orders import submit_assembly_work_order
from services.errors import DomainError
from services.procedure_tags import (
    consume_tag_stock,
    get_or_create_tag,
    get_or_create_tag_set,
    procedure_department_id,
    route_tag_output,
    tag_set_tags,
    target_tag_set,
)
from services.production_movements import record_movement
from services.work_order_presenters import serialize_batch, serialize_work_order
from services.work_order_support import (
    consume_repository,
    mark_order_planned,
    move_to_node,
    node_context,
    refresh_order_closed,
)


def create_work_order(
    repository_id: int | None,
    procedure_tag_stock_id: int | None,
    tag_names: list[str],
    quantity: int,
    worker_id: int | None,
    user_department: str,
) -> dict:
    if (repository_id is None) == (procedure_tag_stock_id is None):
        raise DomainError("work_order_source_invalid", "工单必须且只能选择一个库存来源")
    with SessionLocal.begin() as session:
        source, production_item = _load_source(session, repository_id, procedure_tag_stock_id)
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该部门配件", status_code=403)
        context, node = node_context(session, production_item, source.flow_node_id)
        if node.get("type") != "process":
            raise DomainError("work_order_node_invalid", "只有工艺节点可以开工单")
        procedure = session.get(Procedure, node.get("procedure_id"), with_for_update=True)
        if procedure is None:
            raise DomainError("procedure_not_found", "当前流程工艺不存在")
        if source.department_id != procedure_department_id(session, procedure):
            raise DomainError("work_order_source_department_invalid", "工单来源不属于当前工艺部门")
        _validate_worker(session, worker_id, source.department_id, procedure)

        if procedure.procedure_type == "standard":
            source_tag_set_id = _validate_tag_source(session, source, procedure)
            normalized_tag_names = _normalize_tag_names(tag_names)
            applied_tags = [
                get_or_create_tag(session, procedure, tag_name)
                for tag_name in normalized_tag_names
            ]
            applied_set = get_or_create_tag_set(
                session,
                procedure,
                [tag.id for tag in applied_tags],
            )
            target_set = target_tag_set(
                session, procedure, source_tag_set_id, applied_tags
            )
            order = _create_record(
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
        else:
            if not isinstance(source, Repository):
                raise DomainError("purchase_source_invalid", "外购入库单只能使用待外购数量")
            if any((tag_name or "").strip() for tag_name in tag_names):
                raise DomainError("purchase_tag_not_allowed", "外购入库工单不使用生产标记")
            order = _create_record(
                session,
                source=source,
                production_item=production_item,
                procedure=procedure,
                quantity=quantity,
                worker_id=worker_id,
                work_order_type="purchase_receipt",
            )
        mark_order_planned(session, production_item)
        order.work_order_no = f"WO-{business_now():%Y%m%d}-{order.id:06d}"
        session.flush()
        return serialize_work_order(session, order)


def submit_work_order(
    work_order_id: int,
    quantity: int,
    completion_action: str,
    user_department: str,
) -> dict:
    if completion_action not in {"direct", "qc"}:
        raise DomainError("completion_action_invalid", "请选择直接完成或送 QC")
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open":
            raise DomainError("work_order_closed", "工单已经结单")
        if order.work_order_type == "assembly":
            return submit_assembly_work_order(
                session, order, quantity, completion_action, user_department
            )

        production_item = session.get(ProductionItem, order.production_item_id, with_for_update=True)
        if production_item is None:
            raise DomainError("production_context_missing", "生产项不存在")
        source, _ = _load_order_source(session, order)
        if order.source_flow_node_id is None or source.source_flow_node_id != order.source_flow_node_id:
            raise DomainError("work_order_source_snapshot_invalid", "工单来源快照与当前库存位置不一致")
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该工单", status_code=403)

        context, node = node_context(session, production_item, order.flow_node_id)
        procedure = session.get(Procedure, node.get("procedure_id"))
        if procedure is None:
            raise DomainError("procedure_not_found", "工单所属工艺不存在")
        if order.work_order_type == "tag":
            _validate_tag_order(session, order, source, procedure)
            if completion_action == "direct":
                raise DomainError(
                    "tag_work_order_complete_required",
                    "标准生产工单请使用完成按钮结单",
                )
        elif procedure.procedure_type != "purchase_receipt":
            raise DomainError("work_order_type_invalid", "外购入库工单所属工艺无效")

        remaining = order.quantity - order.completed_quantity
        if quantity <= 0 or quantity > remaining or quantity > source.quantity:
            raise DomainError("submission_quantity_exceeded", "提交数量超过工单剩余数量")
        batch = None
        target_flow_node_id = None
        target_department_id = None
        if completion_action == "qc":
            batch = WorkOrderBatch(
                work_order_id=order.id,
                submitted_quantity=quantity,
                source_flow_node_id=order.source_flow_node_id,
            )
            session.add(batch)
            session.flush()
        else:
            target = context.normal_target(node["id"])
            target_department_id = move_to_node(
                session, production_item, target, quantity, node["id"]
            )
            target_flow_node_id = target.get("id") if target else None

        record_movement(
            session,
            production_item=production_item,
            quantity=quantity,
            movement_type=(
                "purchase_receipt"
                if order.work_order_type == "purchase_receipt"
                else "process"
            ),
            source_flow_node_id=node["id"],
            target_flow_node_id=target_flow_node_id,
            source_tag_set_id=order.source_tag_set_id,
            target_tag_set_id=order.target_tag_set_id,
            source_department_id=source.department_id,
            target_department_id=target_department_id,
            work_order_id=order.id,
            work_order_batch_id=batch.id if batch else None,
        )
        session.flush()
        order.completed_quantity += quantity
        if order.work_order_type != "tag" and quantity == remaining:
            order.status = "closed"
            order.closed_at = utc_now()
        _consume_order_source(session, order, source, quantity)
        session.flush()
        refresh_order_closed(session, production_item)
        return serialize_work_order(session, order)


def complete_work_order(work_order_id: int, user_department: str) -> dict:
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
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权完成该工单", status_code=403)
        _validate_tag_order_snapshot(session, order, procedure, order.source_tag_set_id)

        pending_qc = session.scalar(
            select(func.count(WorkOrderBatch.id)).where(
                WorkOrderBatch.work_order_id == order.id,
                WorkOrderBatch.recorded_at.is_(None),
            )
        ) or 0
        if pending_qc:
            raise DomainError("work_order_qc_pending", "仍有待检批次，不能结单")
        if _rework_pending_quantity(session, order.id):
            raise DomainError("work_order_rework_pending", "仍有返工数量未重新送检，不能结单")

        remaining = order.quantity - order.completed_quantity
        if remaining:
            source, _ = _load_order_source(session, order)
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
            _validate_tag_order(session, order, source, procedure)
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
            _consume_order_source(session, order, source, remaining)

        order.status = "closed"
        order.closed_at = utc_now()
        session.flush()
        refresh_order_closed(session, production_item)
        return serialize_work_order(session, order)


def resubmit_rework_batch(
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

        submitted = session.scalar(
            select(func.coalesce(func.sum(WorkOrderBatch.submitted_quantity), 0)).where(
                WorkOrderBatch.rework_source_batch_id == source_batch.id,
                WorkOrderBatch.work_order_id == order.id,
            )
        ) or 0
        available = source_batch.rework_quantity - submitted
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
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权提交返工送检", status_code=403)
        _validate_tag_order_snapshot(session, order, procedure, order.source_tag_set_id)

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


def cancel_work_order(work_order_id: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open" or order.completed_quantity:
            raise DomainError("work_order_not_cancellable", "只有未提交产量的开放工单可以取消")
        department_id = _source_department_id(session, order)
        department = session.get(Department, department_id) if department_id else None
        department_code = "assembly" if order.work_order_type == "assembly" else (
            department.department_code if department else ""
        )
        if user_department not in {"sys", department_code}:
            raise DomainError("department_access_denied", "无权取消该工单", status_code=403)
        order.status = "cancelled"
        order.closed_at = utc_now()
        session.flush()
        return serialize_work_order(session, order)


def _create_record(
    session,
    *,
    source: Repository | ProcedureTagStock,
    production_item: ProductionItem,
    procedure: Procedure,
    quantity: int,
    worker_id: int | None,
    work_order_type: str,
    applied_tag_set_id: int | None = None,
    applied_tag_names: list[str] | None = None,
    source_tag_set_id: int | None = None,
    target_tag_set_id: int | None = None,
) -> WorkOrder:
    if quantity <= 0:
        raise DomainError("work_order_quantity_invalid", "工单数量必须大于 0")
    repository_id = source.id if isinstance(source, Repository) else None
    tag_stock_id = source.id if isinstance(source, ProcedureTagStock) else None
    reserved = _reserved_quantity(session, repository_id, tag_stock_id)
    if quantity > source.quantity - reserved:
        raise DomainError("work_order_quantity_exceeded", "开单数量超过当前可用数量")
    order = WorkOrder(
        repository_id=repository_id,
        procedure_tag_stock_id=tag_stock_id,
        production_item_id=production_item.id,
        procedure_id=procedure.id,
        applied_tag_set_id=applied_tag_set_id,
        source_tag_set_id=source_tag_set_id,
        target_tag_set_id=target_tag_set_id,
        work_order_type=work_order_type,
        flow_node_id=source.flow_node_id,
        source_flow_node_id=source.source_flow_node_id,
        work_order_name=(
            f"{procedure.procedure_name}-{' + '.join(applied_tag_names)}"
            if applied_tag_names else procedure.procedure_name
        ),
        worker_id=worker_id,
        quantity=quantity,
    )
    session.add(order)
    session.flush()
    return order


def _validate_worker(session, worker_id: int | None, department_id: int, procedure: Procedure) -> None:
    worker = session.get(Worker, worker_id) if worker_id else None
    if worker_id and (
        worker is None
        or worker.department_id != department_id
        or worker.workshop_id != procedure.workshop_id
    ):
        raise DomainError("worker_invalid", "工人不属于当前工艺所在车间")


def _normalize_tag_names(tag_names: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw_name in tag_names:
        name = (raw_name or "").strip()
        if not name or name in normalized:
            continue
        if len(name) > 200:
            raise DomainError("procedure_tag_name_too_long", "生产标记名称不能超过 200 个字符")
        normalized.append(name)
    if not normalized:
        raise DomainError("procedure_applied_tags_empty", "请至少输入一个新增标记")
    if len(normalized) > 20:
        raise DomainError("procedure_applied_tags_too_many", "一张工单最多新增 20 个标记")
    return normalized


def _validate_tag_source(
    session,
    source: Repository | ProcedureTagStock,
    procedure: Procedure,
) -> int | None:
    if isinstance(source, Repository):
        return None
    tag_set = session.get(ProcedureTagSet, source.tag_set_id)
    if tag_set is None or tag_set.procedure_id != procedure.id:
        raise DomainError("procedure_tag_set_invalid", "来源标记组合不属于当前流程工艺")
    return tag_set.id


def _validate_tag_order(session, order: WorkOrder, source, procedure: Procedure) -> None:
    source_tag_set_id = source.tag_set_id if isinstance(source, ProcedureTagStock) else None
    _validate_tag_order_snapshot(session, order, procedure, source_tag_set_id)


def _validate_tag_order_snapshot(
    session,
    order: WorkOrder,
    procedure: Procedure,
    source_tag_set_id: int | None,
) -> None:
    applied_set = session.get(ProcedureTagSet, order.applied_tag_set_id)
    target_set = session.get(ProcedureTagSet, order.target_tag_set_id)
    source_tag_ids = [tag.id for tag in tag_set_tags(session, source_tag_set_id)]
    applied_tag_ids = [tag.id for tag in tag_set_tags(session, order.applied_tag_set_id)]
    target_tag_ids = [tag.id for tag in tag_set_tags(session, order.target_tag_set_id)]
    expected_target_ids = sorted(set(source_tag_ids) | set(applied_tag_ids))
    if (
        procedure.procedure_type != "standard"
        or order.procedure_id != procedure.id
        or applied_set is None
        or applied_set.procedure_id != procedure.id
        or not applied_tag_ids
        or bool(set(applied_tag_ids) & set(source_tag_ids))
        or target_set is None
        or target_set.procedure_id != procedure.id
        or source_tag_set_id != order.source_tag_set_id
        or target_tag_ids != expected_target_ids
    ):
        raise DomainError("procedure_tag_context_invalid", "工单标记组合与当前库存不一致")


def _rework_pending_quantity(session, work_order_id: int) -> int:
    batches = list(
        session.scalars(
            select(WorkOrderBatch).where(WorkOrderBatch.work_order_id == work_order_id)
        ).all()
    )
    submitted_by_source: dict[int, int] = {}
    for batch in batches:
        if batch.rework_source_batch_id is not None:
            submitted_by_source[batch.rework_source_batch_id] = (
                submitted_by_source.get(batch.rework_source_batch_id, 0)
                + batch.submitted_quantity
            )
    return sum(
        max((batch.rework_quantity or 0) - submitted_by_source.get(batch.id, 0), 0)
        for batch in batches
        if batch.recorded_at is not None
    )


def _load_source(session, repository_id, procedure_tag_stock_id):
    source = (
        session.get(Repository, repository_id, with_for_update=True)
        if repository_id is not None
        else session.get(ProcedureTagStock, procedure_tag_stock_id, with_for_update=True)
    )
    if source is None:
        raise DomainError("work_order_source_not_found", "工单来源数量不存在", status_code=404)
    production_item = session.get(ProductionItem, source.production_item_id)
    if production_item is None:
        raise DomainError("production_context_missing", "生产项不存在")
    return source, production_item


def _load_order_source(session, order: WorkOrder):
    if order.repository_id is not None:
        return _load_source(session, order.repository_id, None)
    if order.procedure_tag_stock_id is not None:
        return _load_source(session, None, order.procedure_tag_stock_id)
    raise DomainError("work_order_source_not_found", "工单来源数量已不存在")


def _reserved_quantity(session, repository_id, procedure_tag_stock_id) -> int:
    condition = (
        WorkOrder.repository_id == repository_id
        if repository_id is not None
        else WorkOrder.procedure_tag_stock_id == procedure_tag_stock_id
    )
    orders = session.scalars(select(WorkOrder).where(condition, WorkOrder.status == "open")).all()
    return sum(order.quantity - order.completed_quantity for order in orders)


def _consume_order_source(session, order: WorkOrder, source, quantity: int) -> None:
    if isinstance(source, Repository):
        if source.quantity == quantity:
            order.repository_id = None
            session.flush()
        consume_repository(session, source, quantity)
    else:
        if source.quantity == quantity:
            order.procedure_tag_stock_id = None
            session.flush()
        consume_tag_stock(session, source, quantity)


def _source_department_id(session, order: WorkOrder) -> int | None:
    source = (
        session.get(Repository, order.repository_id)
        if order.repository_id is not None
        else session.get(ProcedureTagStock, order.procedure_tag_stock_id)
    )
    return source.department_id if source else None
