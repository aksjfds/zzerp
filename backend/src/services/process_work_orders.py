from sqlalchemy import select

from database import SessionLocal
from domain.time import business_now, utc_now
from models.organization import Department, Procedure, ProcedureSubstep, Worker
from models.production import (
    ProcedureStageStock,
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderBatch,
)
from services.assembly_work_orders import submit_assembly_work_order
from services.errors import DomainError
from services.procedure_stages import (
    consume_stage_stock,
    get_or_create_substep,
    route_substep_output,
)
from services.production_movements import record_movement
from services.work_order_presenters import serialize_work_order
from services.work_order_support import (
    consume_repository,
    mark_order_planned,
    node_context,
    refresh_order_closed,
)


def create_work_order(
    repository_id: int | None,
    procedure_stage_stock_id: int | None,
    substep_name: str,
    quantity: int,
    worker_id: int | None,
    user_department: str,
) -> dict:
    if (repository_id is None) == (procedure_stage_stock_id is None):
        raise DomainError(
            "work_order_source_invalid",
            "普通工单必须且只能选择一个库存来源",
        )
    with SessionLocal.begin() as session:
        source, production_item = _load_source(
            session,
            repository_id,
            procedure_stage_stock_id,
        )
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该部门配件", status_code=403)

        _, node = node_context(session, production_item, source.flow_node_id)
        if node.get("type") != "process":
            raise DomainError("work_order_node_invalid", "只有工艺节点可以开细分工序工单")
        procedure = session.get(Procedure, node.get("procedure_id"), with_for_update=True)
        if procedure is None:
            raise DomainError("procedure_not_found", "当前流程工艺不存在")
        _validate_stage_source(session, source, procedure)
        substep = get_or_create_substep(session, procedure, substep_name)
        _validate_worker(session, worker_id, source.department_id, procedure)

        order = _create_work_order_record(
            session,
            source=source,
            production_item=production_item,
            procedure=procedure,
            substep=substep,
            quantity=quantity,
            worker_id=worker_id,
        )
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
                session,
                order,
                quantity,
                completion_action,
                user_department,
            )

        production_item = session.get(
            ProductionItem,
            order.production_item_id,
            with_for_update=True,
        )
        if production_item is None:
            raise DomainError("production_context_missing", "生产项不存在")
        source, _ = _load_order_source(session, order)
        source_flow_node_id = order.source_flow_node_id
        if (
            source_flow_node_id is None
            or source.source_flow_node_id != source_flow_node_id
        ):
            raise DomainError(
                "work_order_source_snapshot_invalid",
                "工单来源快照与当前库存位置不一致",
            )
        department = session.get(Department, source.department_id)
        if department is None or user_department not in {"sys", department.department_code}:
            raise DomainError("department_access_denied", "无权操作该工单", status_code=403)
        substep = session.get(ProcedureSubstep, order.substep_id)
        procedure = session.get(Procedure, substep.procedure_id) if substep else None
        if substep is None or procedure is None:
            raise DomainError("procedure_substep_not_found", "工单细分工序不存在")
        _validate_stage_source(session, source, procedure)

        remaining = order.quantity - order.completed_quantity
        if quantity > remaining or quantity > source.quantity:
            raise DomainError("submission_quantity_exceeded", "提交数量超过工单剩余数量")
        is_purchase_receipt = procedure.procedure_type == "purchase_receipt"
        if completion_action == "direct" and quantity != remaining and not is_purchase_receipt:
            raise DomainError("partial_completion_not_allowed", "直接完成必须一次提交剩余数量")

        context, node = node_context(session, production_item, order.flow_node_id)
        if node.get("procedure_id") != procedure.id:
            raise DomainError("procedure_substep_mismatch", "工单细分工序不属于当前流程工艺")

        batch = None
        target_flow_node_id = None
        target_department_id = None
        if completion_action == "qc":
            batch = WorkOrderBatch(
                work_order_id=order.id,
                submitted_quantity=quantity,
                source_flow_node_id=source_flow_node_id,
                source_substep_id=(
                    source.completed_substep_id
                    if isinstance(source, ProcedureStageStock)
                    else None
                ),
            )
            session.add(batch)
            session.flush()
        else:
            target_flow_node_id, target_department_id, _ = route_substep_output(
                session,
                production_item=production_item,
                flow_context=context,
                flow_node_id=node["id"],
                source_flow_node_id=source_flow_node_id,
                substep=substep,
                quantity=quantity,
            )

        record_movement(
            session,
            production_item=production_item,
            quantity=quantity,
            movement_type="purchase_receipt" if is_purchase_receipt else "process",
            source_flow_node_id=node["id"],
            target_flow_node_id=target_flow_node_id,
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
        _consume_order_source(session, order, source, quantity)
        session.flush()
        refresh_order_closed(session, production_item)
        return serialize_work_order(session, order)


def cancel_work_order(work_order_id: int, user_department: str) -> dict:
    with SessionLocal.begin() as session:
        order = session.get(WorkOrder, work_order_id, with_for_update=True)
        if order is None:
            raise DomainError("work_order_not_found", "工单不存在", status_code=404)
        if order.status != "open":
            raise DomainError("work_order_not_cancellable", "只有未完成工单可以取消")
        if order.completed_quantity:
            raise DomainError("work_order_started", "已经提交过产量的工单不能取消")
        if order.work_order_type == "assembly":
            department_code = "assembly"
        else:
            substep = session.get(ProcedureSubstep, order.substep_id)
            procedure = session.get(Procedure, substep.procedure_id) if substep else None
            department = (
                session.get(Department, _source_department_id(session, order))
                if procedure is not None
                else None
            )
            department_code = department.department_code if department else ""
        if user_department not in {"sys", department_code}:
            raise DomainError("department_access_denied", "无权取消该工单", status_code=403)
        order.status = "cancelled"
        order.closed_at = utc_now()
        session.flush()
        return serialize_work_order(session, order)


def _create_work_order_record(
    session,
    *,
    source: Repository | ProcedureStageStock,
    production_item: ProductionItem,
    procedure: Procedure,
    substep: ProcedureSubstep,
    quantity: int,
    worker_id: int | None,
) -> WorkOrder:
    if quantity <= 0:
        raise DomainError("work_order_quantity_invalid", "工单数量必须大于 0")
    repository_id = source.id if isinstance(source, Repository) else None
    stage_stock_id = source.id if isinstance(source, ProcedureStageStock) else None
    reserved = _reserved_quantity(
        session,
        repository_id=repository_id,
        procedure_stage_stock_id=stage_stock_id,
    )
    if quantity > source.quantity - reserved:
        raise DomainError("work_order_quantity_exceeded", "开单数量超过当前可用数量")

    order = WorkOrder(
        repository_id=repository_id,
        procedure_stage_stock_id=stage_stock_id,
        production_item_id=production_item.id,
        substep_id=substep.id,
        work_order_type="substep",
        work_order_name=f"{procedure.procedure_name}-{substep.substep_name}",
        flow_node_id=source.flow_node_id,
        source_flow_node_id=source.source_flow_node_id,
        worker_id=worker_id,
        quantity=quantity,
    )
    session.add(order)
    session.flush()
    mark_order_planned(session, production_item)
    order.work_order_no = f"WO-{business_now():%Y%m%d}-{order.id:06d}"
    session.flush()
    return order


def _validate_worker(
    session,
    worker_id: int | None,
    department_id: int,
    procedure: Procedure,
) -> None:
    worker = session.get(Worker, worker_id) if worker_id else None
    if worker_id and (
        worker is None
        or worker.department_id != department_id
        or worker.workshop_id != procedure.workshop_id
    ):
        raise DomainError("worker_invalid", "工人不属于当前工艺所在车间")


def _validate_stage_source(
    session,
    source: Repository | ProcedureStageStock,
    procedure: Procedure,
) -> None:
    if not isinstance(source, ProcedureStageStock):
        return
    completed_substep = session.get(ProcedureSubstep, source.completed_substep_id)
    if completed_substep is None or completed_substep.procedure_id != procedure.id:
        raise DomainError("procedure_stage_mismatch", "细分工序数量不属于当前流程工艺")


def _load_source(session, repository_id, procedure_stage_stock_id):
    if repository_id is not None:
        source = session.get(Repository, repository_id, with_for_update=True)
    else:
        source = session.get(
            ProcedureStageStock,
            procedure_stage_stock_id,
            with_for_update=True,
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
    if order.procedure_stage_stock_id is not None:
        return _load_source(session, None, order.procedure_stage_stock_id)
    raise DomainError("work_order_source_not_found", "工单来源数量已不存在")


def _reserved_quantity(session, *, repository_id, procedure_stage_stock_id) -> int:
    condition = (
        WorkOrder.repository_id == repository_id
        if repository_id is not None
        else WorkOrder.procedure_stage_stock_id == procedure_stage_stock_id
    )
    orders = session.scalars(
        select(WorkOrder).where(condition, WorkOrder.status == "open")
    ).all()
    return sum(item.quantity - item.completed_quantity for item in orders)


def _consume_order_source(session, order: WorkOrder, source, quantity: int) -> None:
    if isinstance(source, Repository):
        if source.quantity == quantity:
            order.repository_id = None
            session.flush()
        consume_repository(session, source, quantity)
    else:
        if source.quantity == quantity:
            order.procedure_stage_stock_id = None
            session.flush()
        consume_stage_stock(session, source, quantity)


def _source_department_id(session, order: WorkOrder) -> int | None:
    if order.repository_id is not None:
        source = session.get(Repository, order.repository_id)
    else:
        source = session.get(ProcedureStageStock, order.procedure_stage_stock_id)
    return source.department_id if source else None
