"""Planning collaboration port used by customer-order orchestration."""

from sqlalchemy import select

from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.plan_builder import planned_product_quantity, rebuild_order_plan
from modules.sales.context_api import OrderPlanState


def order_plan_states(
    session,
    order_ids: set[int],
) -> dict[int, OrderPlanState]:
    if not order_ids:
        return {}
    return {
        plan.customer_order_id: OrderPlanState(plan.status, plan.confirmed_at)
        for plan in session.scalars(
            select(ProductionPlan).where(
                ProductionPlan.customer_order_id.in_(order_ids)
            )
        )
    }


def order_plan_state(
    session,
    order_id: int,
    *,
    for_update: bool = False,
) -> OrderPlanState | None:
    statement = select(ProductionPlan).where(
        ProductionPlan.customer_order_id == order_id
    )
    if for_update:
        statement = statement.with_for_update()
    plan = session.scalar(statement)
    return OrderPlanState(plan.status, plan.confirmed_at) if plan is not None else None


def planned_product_quantities(
    session,
    customer_order_item_ids: list[int],
) -> dict[int, int]:
    if not customer_order_item_ids:
        return {}
    grouped: dict[int, list[ProductionPlanItem]] = {}
    for item in session.scalars(
        select(ProductionPlanItem).where(
            ProductionPlanItem.customer_order_item_id.in_(customer_order_item_ids)
        )
    ):
        grouped.setdefault(item.customer_order_item_id, []).append(item)
    return {
        order_item_id: planned_product_quantity(items)
        for order_item_id, items in grouped.items()
    }


def delete_order_plan(session, order_id: int) -> None:
    plan = session.scalar(
        select(ProductionPlan)
        .where(ProductionPlan.customer_order_id == order_id)
        .with_for_update()
    )
    if plan is not None:
        session.delete(plan)
        session.flush()


__all__ = [
    "delete_order_plan",
    "order_plan_state",
    "order_plan_states",
    "planned_product_quantities",
    "rebuild_order_plan",
]
