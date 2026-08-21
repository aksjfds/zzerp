"""Production-core read context required by quality workflows."""

from sqlalchemy.orm import Session

from modules.production_core.context_api import (
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.persistence import (
    ProductionItem,
    WorkOrder,
)


def load_qc_work_order(
    session: Session,
    work_order_id: int,
    *,
    for_update: bool = False,
) -> WorkOrderContext | None:
    return session.get(WorkOrder, work_order_id, with_for_update=for_update)


def load_qc_production_item(
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


__all__ = [
    "load_qc_production_item",
    "load_qc_work_order",
]
