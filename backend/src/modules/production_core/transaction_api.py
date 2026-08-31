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
from modules.production_core.work_order_commands import (
    cancel_open_order,
    ensure_source_procedure_not_repeated,
    load_order_source,
    load_source,
    prepare_full_submission,
    validate_completion_action,
    validate_worker,
)


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


def record_work_order_submission(order: WorkOrderContext, quantity: int) -> None:
    order.completed_quantity += quantity
    order.processed_quantity = order.completed_quantity


__all__ = [
    "cancel_open_order",
    "ensure_source_procedure_not_repeated",
    "load_order_source",
    "load_source",
    "load_production_item_context",
    "load_work_order_context",
    "prepare_full_submission",
    "record_work_order_submission",
    "validate_completion_action",
    "validate_worker",
]
