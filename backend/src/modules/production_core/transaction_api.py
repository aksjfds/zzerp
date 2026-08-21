"""Transaction-aware production contexts and owner commands.

Collaborating modules use these functions instead of importing production
persistence classes. Concrete ORM objects satisfy the persistence-free
protocols declared in ``context_api.py``.
"""

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


__all__ = [
    "load_production_item_context",
    "load_work_order_context",
]
