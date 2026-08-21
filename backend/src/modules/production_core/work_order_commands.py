from sqlalchemy import select

from modules.organization.model_api import Department, Procedure
from modules.production_core.persistence import ProductionItem, Repository, WorkOrder
from modules.errors import DomainError
from modules.production_core.work_order_progress import order_has_submissions, order_remaining_quantity
from modules.production_core.work_order_support import consume_repository
from modules.workforce.reference_api import get_worker_reference


InventorySource = Repository


def create_order_record(
    session,
    *,
    source: InventorySource,
    production_item: ProductionItem,
    procedure: Procedure,
    quantity: int,
    worker_id: int | None,
    work_order_type: str,
    remark: str | None = None,
) -> WorkOrder:
    if quantity <= 0:
        raise DomainError("work_order_quantity_invalid", "工单数量必须大于 0")
    repository_id = source.id if isinstance(source, Repository) else None
    reserved = reserved_source_quantity(session, repository_id)
    if quantity > source.quantity - reserved:
        raise DomainError("work_order_quantity_exceeded", "开单数量超过当前可用数量")
    order = WorkOrder(
        repository_id=repository_id,
        production_item_id=production_item.id,
        procedure_id=procedure.id,
        work_order_type=work_order_type,
        flow_node_id=source.flow_node_id,
        source_flow_node_id=source.source_flow_node_id,
        work_order_name=procedure.procedure_name,
        remark=(remark or "").strip() or None,
        worker_id=worker_id,
        quantity=quantity,
    )
    session.add(order)
    session.flush()
    return order


def validate_worker(
    session,
    worker_id: int | None,
    department_id: int,
    procedure: Procedure,
) -> None:
    worker = get_worker_reference(session, worker_id) if worker_id else None
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


def reserved_source_quantity(
    session,
    repository_id: int | None,
) -> int:
    condition = WorkOrder.repository_id == repository_id
    orders = session.scalars(
        select(WorkOrder).where(condition, WorkOrder.status == "open")
    ).all()
    return sum(order_remaining_quantity(order) for order in orders)


def consume_order_source(
    session,
    order: WorkOrder,
    source: InventorySource,
    quantity: int,
) -> None:
    if source.quantity == quantity:
        order.repository_id = None
        session.flush()
    consume_repository(session, source, quantity)


def source_department_id(session, order: WorkOrder) -> int | None:
    source = session.get(Repository, order.repository_id) if order.repository_id else None
    return source.department_id if source else None


def cancel_open_order(session, order: WorkOrder, user_department: str, closed_at) -> None:
    if order.status != "open" or order_has_submissions(order):
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
    if user_department not in {"sys", department_code}:
        raise DomainError("department_access_denied", "无权取消该工单", status_code=403)
    order.status = "cancelled"
    order.closed_at = closed_at
    session.flush()
