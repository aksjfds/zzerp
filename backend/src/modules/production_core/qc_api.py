"""Production-core read context required by quality workflows."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.production_types import MOVEMENT_QC_DISPATCH
from modules.production_core.context_api import (
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
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


def dispatched_qc_quantity(session: Session, work_order_batch_id: int) -> int:
    return int(
        session.scalar(
            select(func.coalesce(func.sum(ProductionMovement.quantity), 0)).where(
                ProductionMovement.work_order_batch_id == work_order_batch_id,
                ProductionMovement.movement_type == MOVEMENT_QC_DISPATCH,
            )
        )
        or 0
    )


__all__ = [
    "dispatched_qc_quantity",
    "load_qc_production_item",
    "load_qc_work_order",
]
