from sqlalchemy import func, select

from modules.production_core.persistence import ProductionItem, WorkOrder, WorkOrderBatch
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.errors import DomainError
from modules.production_core.repositories import provision_order_repositories
from modules.production_core.work_order_progress import order_has_submissions


def initialize_order_production(
    session,
    order: CustomerOrder,
    *,
    part_quantities: dict[tuple[int, int, str], int] | None = None,
) -> None:
    provision_order_repositories(
        session,
        order,
        part_quantities=part_quantities,
    )


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


def rollback_unstarted_order_production(session, order: CustomerOrder) -> None:
    work_order_id = session.scalar(
        select(WorkOrder.id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(CustomerOrderItem.customer_order_id == order.id)
        .limit(1)
    )
    if work_order_id is not None:
        raise DomainError(
            "production_plan_work_order_exists",
            "生产计划已经创建工单，不能撤回确认",
            status_code=409,
        )
    session.scalar(
        select(func.set_config(
            "zzerp.plan_unconfirm_order_id",
            str(order.id),
            True,
        ))
    )
    production_items = list(session.scalars(
        select(ProductionItem)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(CustomerOrderItem.customer_order_id == order.id)
        .with_for_update()
    ))
    for production_item in production_items:
        session.delete(production_item)
