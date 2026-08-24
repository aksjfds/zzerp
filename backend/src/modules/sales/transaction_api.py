"""Transaction-aware customer-order state changes for application workflows."""

from domain.time import utc_now
from modules.sales.persistence import CustomerOrder, CustomerOrderItem


def mark_order_planned(session, customer_order_item_id: int) -> None:
    order_item = session.get(CustomerOrderItem, customer_order_item_id)
    if order_item is None:
        return
    customer_order = session.get(
        CustomerOrder,
        order_item.customer_order_id,
        with_for_update=True,
    )
    if customer_order is not None and customer_order.status == "confirmed":
        customer_order.status = "planned"
        customer_order.revision += 1
        customer_order.updated_at = utc_now()


def close_fully_shipped_order(session, order_id: int) -> None:
    order = session.get(CustomerOrder, order_id, with_for_update=True)
    if order is None or order.status != "planned":
        return
    order.status = "closed"
    order.revision += 1
    order.updated_at = utc_now()


def restore_order_state(
    session,
    order_id: int,
    *,
    status: str,
    revision: int,
) -> None:
    order = session.get(CustomerOrder, order_id, with_for_update=True)
    if order is None:
        return
    order.status = status
    order.revision = revision


__all__ = [
    "close_fully_shipped_order",
    "mark_order_planned",
    "restore_order_state",
]
