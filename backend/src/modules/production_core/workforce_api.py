"""Immutable production projections used by workforce reporting."""

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.production_core.persistence import ProductionItem, WorkOrder
from modules.production_core.work_order_presenters import item_display


@dataclass(frozen=True, slots=True)
class WorkOrderActivity:
    id: int
    work_order_no: str | None
    production_item_id: int
    procedure_id: int | None
    work_order_type: str
    work_order_name: str
    worker_id: int | None
    quantity: int
    processed_quantity: int
    completed_quantity: int
    status: str
    created_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProductionItemDisplay:
    id: int
    product_id: int
    item_name: str


def _work_order_activity(order: WorkOrder) -> WorkOrderActivity:
    return WorkOrderActivity(
        id=order.id,
        work_order_no=order.work_order_no,
        production_item_id=order.production_item_id,
        procedure_id=order.procedure_id,
        work_order_type=order.work_order_type,
        work_order_name=order.work_order_name,
        worker_id=order.worker_id,
        quantity=order.quantity,
        processed_quantity=order.processed_quantity,
        completed_quantity=order.completed_quantity,
        status=order.status,
        created_at=order.created_at,
        closed_at=order.closed_at,
    )


def list_worker_activity_orders(
    session: Session,
    worker_id: int,
    month_start: datetime,
    month_end: datetime,
) -> list[WorkOrderActivity]:
    activity_at = func.coalesce(WorkOrder.closed_at, WorkOrder.created_at)
    orders = session.scalars(
        select(WorkOrder)
        .where(
            WorkOrder.worker_id == worker_id,
            WorkOrder.status != "cancelled",
            activity_at >= month_start,
            activity_at < month_end,
        )
        .order_by(activity_at.desc(), WorkOrder.id.desc())
    ).all()
    return [_work_order_activity(order) for order in orders]


def list_work_order_activities(
    session: Session,
    work_order_ids: Collection[int],
    *,
    worker_id: int | None = None,
    work_order_type: str | None = None,
) -> list[WorkOrderActivity]:
    if not work_order_ids:
        return []
    statement = select(WorkOrder).where(
        WorkOrder.id.in_(work_order_ids),
        WorkOrder.status != "cancelled",
    )
    if worker_id is not None:
        statement = statement.where(WorkOrder.worker_id == worker_id)
    if work_order_type is not None:
        statement = statement.where(WorkOrder.work_order_type == work_order_type)
    return [
        _work_order_activity(order)
        for order in session.scalars(statement).all()
    ]


def get_production_item_display(
    session: Session,
    production_item_id: int,
) -> ProductionItemDisplay | None:
    production_item = session.get(ProductionItem, production_item_id)
    if production_item is None:
        return None
    _, item_name = item_display(session, production_item)
    return ProductionItemDisplay(
        id=production_item.id,
        product_id=production_item.product_id,
        item_name=item_name,
    )


__all__ = [
    "ProductionItemDisplay",
    "WorkOrderActivity",
    "get_production_item_display",
    "list_work_order_activities",
    "list_worker_activity_orders",
]
