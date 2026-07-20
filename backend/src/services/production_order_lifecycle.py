from sqlalchemy import func, select

from models.production import ProductionItem, WorkOrder, WorkOrderBatch
from models.sales import CustomerOrder, CustomerOrderItem
from services.errors import DomainError
from services.production_repositories import provision_order_repositories
from services.work_order_progress import order_has_submissions


def initialize_order_production(session, order: CustomerOrder) -> None:
    provision_order_repositories(session, order)


def cancel_order_production(session, order: CustomerOrder) -> None:
    work_orders = session.scalars(
        select(WorkOrder)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(CustomerOrderItem.customer_order_id == order.id)
    ).all()
    if any(order_has_submissions(item) for item in work_orders):
        raise DomainError("customer_order_started", "订单已经产生生产完成数量，不能取消")
    if work_orders:
        batch_count = session.scalar(
            select(func.count(WorkOrderBatch.id)).where(
                WorkOrderBatch.work_order_id.in_([item.id for item in work_orders])
            )
        )
        if batch_count:
            raise DomainError("customer_order_started", "订单已经送检，不能取消")
    for work_order in work_orders:
        session.delete(work_order)
    # Remove work-order/material references before production-item cascades
    # delete their repositories and initial movement rows.
    session.flush()
    production_items = session.scalars(
        select(ProductionItem)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(CustomerOrderItem.customer_order_id == order.id)
    ).all()
    for production_item in production_items:
        session.delete(production_item)
