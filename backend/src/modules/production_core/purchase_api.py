"""Production-core commands used by purchase-receipt workflows."""

from domain.production_types import WORK_ORDER_STATUS_CLOSED
from domain.time import utc_now
from modules.production_core.persistence import (
    ProductionItem,
    Repository,
    WorkOrder,
)
from modules.production_core.work_order_commands import consume_order_source
from modules.production_core.work_order_presenters import serialize_work_order
from modules.production_core.work_order_progress import order_remaining_quantity


def is_repository_source(source: object) -> bool:
    return isinstance(source, Repository)


def finalize_purchase_submission(
    session,
    *,
    order: WorkOrder,
    source: object,
    production_item: ProductionItem,
    quantity: int,
) -> dict:
    remaining = order_remaining_quantity(order)
    session.flush()
    order.completed_quantity += quantity
    if quantity == remaining:
        order.status = WORK_ORDER_STATUS_CLOSED
        order.closed_at = utc_now()
    consume_order_source(session, order, source, quantity)
    session.flush()
    return serialize_work_order(session, order)


__all__ = ["finalize_purchase_submission", "is_repository_source"]
