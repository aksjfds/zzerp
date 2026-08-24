"""Production read models exposed to the sales module."""

from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.production_core.model_api import ProductionItem, ProductionMovement
from modules.planning.order_status_view import get_customer_order_production


def order_item_shipped_quantities(
    session: Session,
    customer_order_item_ids: Collection[int],
) -> dict[int, int]:
    if not customer_order_item_ids:
        return {}
    return {
        order_item_id: int(quantity)
        for order_item_id, quantity in session.execute(
            select(
                ProductionItem.customer_order_item_id,
                func.coalesce(func.sum(ProductionMovement.quantity), 0),
            )
            .join(
                ProductionMovement,
                ProductionMovement.production_item_id == ProductionItem.id,
            )
            .where(
                ProductionItem.customer_order_item_id.in_(customer_order_item_ids),
                ProductionMovement.movement_type == "customer_shipment",
            )
            .group_by(ProductionItem.customer_order_item_id)
        )
    }


__all__ = [
    "get_customer_order_production",
    "order_item_shipped_quantities",
]
