"""Transaction-aware production contexts and owner commands.

Collaborating modules use these functions instead of importing production
persistence classes. Concrete ORM objects satisfy the persistence-free
protocols declared in ``context_api.py``.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.production_core.context_api import (
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.persistence import ProductionItem, WorkOrder


def load_production_item_context(
    session: Session,
    production_item_id: int,
    *,
    for_update: bool = False,
) -> ProductionItemContext | None:
    return session.get(
        ProductionItem,
        production_item_id,
        with_for_update=for_update,
    )


def load_work_order_context(
    session: Session,
    work_order_id: int,
    *,
    for_update: bool = False,
) -> WorkOrderContext | None:
    return session.get(
        WorkOrder,
        work_order_id,
        with_for_update=for_update,
    )


def clear_procedure_tag_stock_references(
    session: Session,
    procedure_tag_stock_id: int,
) -> None:
    orders = session.scalars(
        select(WorkOrder)
        .where(WorkOrder.procedure_tag_stock_id == procedure_tag_stock_id)
        .with_for_update()
    ).all()
    for order in orders:
        order.procedure_tag_stock_id = None


__all__ = [
    "clear_procedure_tag_stock_references",
    "load_production_item_context",
    "load_work_order_context",
]
