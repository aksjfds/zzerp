"""Stable planning references exposed to collaborating modules."""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.planning.persistence import ProductionPlan, ProductionPlanItem


def list_confirmed_assembly_plan_quantities(
    session: Session,
    customer_order_item_ids: Collection[int],
) -> list[tuple[int, str, int]]:
    """Return confirmed assembly quantities without exposing planning models."""
    if not customer_order_item_ids:
        return []
    return [
        (order_item_id, flow_node_id, int(planned_quantity))
        for order_item_id, flow_node_id, planned_quantity in session.execute(
            select(
                ProductionPlanItem.customer_order_item_id,
                ProductionPlanItem.flow_node_id,
                ProductionPlanItem.planned_production_quantity,
            )
            .join(
                ProductionPlan,
                ProductionPlan.id == ProductionPlanItem.production_plan_id,
            )
            .where(
                ProductionPlan.status == "confirmed",
                ProductionPlanItem.item_type == "assembly",
                ProductionPlanItem.customer_order_item_id.in_(
                    customer_order_item_ids
                ),
            )
        )
    ]


__all__ = ["list_confirmed_assembly_plan_quantities"]
