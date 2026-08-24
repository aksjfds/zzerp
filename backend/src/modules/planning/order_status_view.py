"""Customer-order production read-model orchestration."""

from sqlalchemy import select

from database import SessionLocal
from modules.errors import DomainError
from modules.planning.order_production_context import (
    _load_order_production_context,
)
from modules.planning.order_production_mapper import _serialize_order_item
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


def get_customer_order_production(order_id: int) -> dict:
    with SessionLocal() as session:
        order = session.get(CustomerOrder, order_id)
        if order is None:
            raise DomainError(
                "customer_order_not_found",
                "客户订单不存在",
                status_code=404,
            )
        order_items = list(session.scalars(
            select(CustomerOrderItem).where(
                CustomerOrderItem.customer_order_id == order.id
            )
        ))
        context = _load_order_production_context(session, order_items)
        return {
            "customer_order_id": order.id,
            "status": order.status,
            "products": [
                _serialize_order_item(context, item)
                for item in order_items
            ],
        }


__all__ = ["get_customer_order_production"]
