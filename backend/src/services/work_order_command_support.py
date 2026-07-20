from sqlalchemy import select

from models.organization import Department, Procedure, Worker
from models.production import (
    ProcedureTagStock,
    ProductionItem,
    Repository,
    WorkOrder,
)
from services.errors import DomainError
from services.procedure_tags import consume_tag_stock
from services.work_order_progress import order_has_submissions, order_remaining_quantity
from services.work_order_support import consume_repository


InventorySource = Repository | ProcedureTagStock


def create_order_record(
    session,
    *,
    source: InventorySource,
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
    reserved = reserved_source_quantity(session, repository_id, tag_stock_id)
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


def validate_worker(
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


def load_source(
    session,
    repository_id: int | None,
    procedure_tag_stock_id: int | None,
) -> tuple[InventorySource, ProductionItem]:
    source = (
        session.get(Repository, repository_id, with_for_update=True)
        if repository_id is not None
        else session.get(
            ProcedureTagStock,
            procedure_tag_stock_id,
            with_for_update=True,
        )
    )
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
        source, _ = load_source(session, order.repository_id, None)
    elif order.procedure_tag_stock_id is not None:
        source, _ = load_source(session, None, order.procedure_tag_stock_id)
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
    procedure_tag_stock_id: int | None,
) -> int:
    condition = (
        WorkOrder.repository_id == repository_id
        if repository_id is not None
        else WorkOrder.procedure_tag_stock_id == procedure_tag_stock_id
    )
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


def source_department_id(session, order: WorkOrder) -> int | None:
    source = (
        session.get(Repository, order.repository_id)
        if order.repository_id is not None
        else session.get(ProcedureTagStock, order.procedure_tag_stock_id)
    )
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
