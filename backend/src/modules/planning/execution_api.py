"""Transaction-aware production-plan guards for execution workflows."""

from sqlalchemy import select

from modules.errors import DomainError
from modules.planning.persistence import ProductionPlan
from modules.sales.model_api import CustomerOrderItem


def ensure_production_plan_active(session, customer_order_item_id: int) -> None:
    order_item = session.get(CustomerOrderItem, customer_order_item_id)
    plan_id = (
        session.scalar(
            select(ProductionPlan.id).where(
                ProductionPlan.customer_order_id == order_item.customer_order_id,
                ProductionPlan.status.in_(("confirmed", "completed")),
            )
        )
        if order_item is not None
        else None
    )
    if plan_id is None:
        raise DomainError(
            "production_plan_not_active",
            "生产计划尚未确认或已经取消，不能开工单",
            status_code=409,
        )


__all__ = [
    "ensure_production_plan_active",
]
