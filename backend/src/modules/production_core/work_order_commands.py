from collections.abc import Collection
from typing import cast

from sqlalchemy import select

from domain.production_types import (
    COMPLETION_DIRECT,
    COMPLETION_QC,
    STANDARD_EXECUTION_WORK_ORDER_TYPES,
    WORK_ORDER_STATUS_CANCELLED,
    WORK_ORDER_STATUS_OPEN,
    WorkOrderCompletionAction,
)
from domain.identity import can_access_department
from domain.workforce import WorkerReference
from modules.organization.model_api import Department, Procedure
from modules.production_core.context_api import WorkOrderContext
from modules.production_core.persistence import ProductionItem, Repository, WorkOrder
from modules.errors import DomainError
from modules.production_core.work_order_progress import order_has_submissions
from modules.production_core.work_order_status import reserved_quantities
from modules.production_core.work_order_support import consume_repository


InventorySource = Repository


def validate_completion_action(
    completion_action: str,
) -> WorkOrderCompletionAction:
    if completion_action not in {COMPLETION_DIRECT, COMPLETION_QC}:
        raise DomainError(
            "completion_action_invalid",
            "请选择直接填写结果或送QC",
        )
    return cast(WorkOrderCompletionAction, completion_action)


def prepare_full_submission(
    order: WorkOrderContext,
    quantity: int,
) -> None:
    """Validate and prepare the only supported initial submission: the full order."""
    if order.work_order_type not in STANDARD_EXECUTION_WORK_ORDER_TYPES:
        raise DomainError("work_order_type_invalid", "工单类型无效")
    if quantity <= 0 or quantity != order.quantity or order.completed_quantity != 0:
        raise DomainError(
            "work_order_full_quantity_required",
            "工单必须一次处理全部数量",
        )
    if order.processed_quantity != 0:
        raise DomainError(
            "work_order_submission_state_invalid",
            "工单当前状态不能提交结果",
        )
    order.processed_quantity = order.quantity


def create_order_record(
    session,
    *,
    source: InventorySource,
    production_item: ProductionItem,
    procedure: Procedure,
    quantity: int,
    worker_id: int | None,
    worker_name: str | None,
    created_by: str,
    work_order_type: str,
    is_temporary: bool,
    remark: str | None = None,
) -> WorkOrder:
    if quantity <= 0:
        raise DomainError("work_order_quantity_invalid", "工单数量必须大于 0")
    ensure_source_procedure_not_repeated(
        session,
        {source.source_work_order_id},
        source.flow_node_id,
        procedure.id,
    )
    repository_id = source.id if isinstance(source, Repository) else None
    reserved = reserved_quantities(session, [repository_id]).get(repository_id, 0)
    if quantity > source.quantity - reserved:
        raise DomainError("work_order_quantity_exceeded", "开单数量超过当前可用数量")
    order = WorkOrder(
        repository_id=repository_id,
        production_item_id=production_item.id,
        procedure_id=procedure.id,
        work_order_type=work_order_type,
        is_temporary=is_temporary,
        flow_node_id=source.flow_node_id,
        source_flow_node_id=source.source_flow_node_id,
        work_order_name=procedure.procedure_name,
        created_by=created_by,
        remark=(remark or "").strip() or None,
        worker_id=worker_id,
        worker_name=worker_name,
        quantity=quantity,
    )
    session.add(order)
    session.flush()
    return order


def ensure_source_procedure_not_repeated(
    session,
    source_work_order_ids: Collection[int | None],
    flow_node_id: str,
    procedure_id: int,
) -> None:
    source_ids = {
        order_id
        for order_id in source_work_order_ids
        if order_id is not None
    }
    if not source_ids:
        return
    repeated_order_id = session.scalar(
        select(WorkOrder.id).where(
            WorkOrder.id.in_(source_ids),
            WorkOrder.flow_node_id == flow_node_id,
            WorkOrder.procedure_id == procedure_id,
        )
    )
    if repeated_order_id is not None:
        raise DomainError(
            "work_order_procedure_repeated",
            "该批物料已经完成所选工艺，请选择其他工艺",
            status_code=409,
        )


def validate_worker(
    worker_id: int | None,
    worker: WorkerReference | None,
    department_id: int,
    procedure: Procedure,
) -> None:
    if worker_id and (
        worker is None
        or worker.department_id != department_id
        or worker.workshop_id != procedure.workshop_id
    ):
        raise DomainError("worker_invalid", "工人不属于当前工艺所在车间")


def load_source(
    session,
    repository_id: int | None,
) -> tuple[InventorySource, ProductionItem]:
    source = session.get(Repository, repository_id, with_for_update=True)
    if source is None:
        raise DomainError(
            "work_order_source_not_found",
            "工单来源数量不存在",
            status_code=404,
        )
    production_item = session.get(ProductionItem, source.production_item_id)
    if production_item is None:
        raise DomainError("production_context_missing", "生产项不存在")
    return source, production_item


def load_order_source(
    session,
    order: WorkOrder,
) -> tuple[InventorySource, ProductionItem]:
    if order.repository_id is not None:
        source, _ = load_source(session, order.repository_id)
    else:
        raise DomainError("work_order_source_not_found", "工单来源数量已不存在")
    production_item = session.get(
        ProductionItem,
        source.production_item_id,
        with_for_update=True,
    )
    if production_item is None:
        raise DomainError("production_context_missing", "生产项不存在")
    return source, production_item


def consume_order_source(
    session,
    order: WorkOrder,
    source: InventorySource,
    quantity: int,
) -> None:
    if source.quantity == quantity or order.completed_quantity >= order.quantity:
        order.repository_id = None
        session.flush()
    consume_repository(session, source, quantity)


def source_department_id(session, order: WorkOrder) -> int | None:
    source = session.get(Repository, order.repository_id) if order.repository_id else None
    return source.department_id if source else None


def cancel_open_order(
    session,
    order: WorkOrder,
    user_department: str | None,
    user_is_system: bool,
    closed_at,
) -> None:
    if order.status != WORK_ORDER_STATUS_OPEN or order_has_submissions(order):
        raise DomainError(
            "work_order_not_cancellable",
            "只有未提交产量的开放工单可以取消",
        )
    department_id = source_department_id(session, order)
    department = session.get(Department, department_id) if department_id else None
    department_code = (
        "assembly"
        if order.work_order_type == "assembly"
        else department.department_code if department else ""
    )
    if not can_access_department(
        user_department,
        user_is_system,
        department_code,
    ):
        raise DomainError("department_access_denied", "无权取消该工单", status_code=403)
    order.repository_id = None
    order.status = WORK_ORDER_STATUS_CANCELLED
    order.closed_at = closed_at
    session.flush()
