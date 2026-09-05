"""Inventory-owned checks and reversals used by production-plan correction."""

from sqlalchemy import case, func, select
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session

from domain.warehouse import WAREHOUSE_OPERATION_SUCCEEDED
from modules.errors import DomainError
from modules.inventory.persistence import FinishedStockTransaction, WarehouseOperation
from modules.inventory.warehouse_api import reverse_warehouse_operation_group
from modules.production_core.model_api import ProductionItem
from modules.sales.model_api import CustomerOrderItem


def ensure_order_has_no_shipments(session: Session, customer_order_id: int) -> None:
    shipped_quantity = session.scalar(
        select(func.coalesce(func.sum(case(
            (
                FinishedStockTransaction.transaction_type == "customer_shipment",
                FinishedStockTransaction.quantity,
            ),
            else_=-FinishedStockTransaction.quantity,
        )), 0))
        .where(
            FinishedStockTransaction.customer_order_id == customer_order_id,
            FinishedStockTransaction.transaction_type.in_((
                "customer_shipment",
                "customer_shipment_reversal",
            )),
        )
    ) or 0
    if shipped_quantity > 0:
        raise DomainError(
            "production_plan_already_shipped",
            "该生产计划对应订单已经发货，不能撤回确认",
            status_code=409,
        )


def reverse_plan_warehouse_issues(
    session: Session,
    *,
    production_plan_id: int,
    actor_username: str,
) -> None:
    reversal = aliased(WarehouseOperation)
    group_numbers = list(session.scalars(
        select(WarehouseOperation.operation_group_no)
        .where(
            WarehouseOperation.production_plan_id == production_plan_id,
            WarehouseOperation.source_type == "plan_confirmation",
            WarehouseOperation.status == WAREHOUSE_OPERATION_SUCCEEDED,
            ~select(reversal.id)
            .where(reversal.reversal_of_operation_id == WarehouseOperation.id)
            .exists(),
        )
        .distinct()
        .order_by(WarehouseOperation.operation_group_no)
    ))
    for group_no in group_numbers:
        result = reverse_warehouse_operation_group(
            session,
            original_group_no=group_no,
            reversal_group_no=f"{group_no}:reversal",
            actor_username=actor_username,
        )
        if result.status != WAREHOUSE_OPERATION_SUCCEEDED:
            raise DomainError(
                "production_plan_warehouse_reversal_failed",
                result.error_message or "生产计划仓库出库冲销失败",
                status_code=409,
            )


def ensure_no_completed_plan_storage(
    session: Session,
    *,
    customer_order_id: int,
    completed_at,
) -> None:
    reversal = aliased(WarehouseOperation)
    stored_id = session.scalar(
        select(WarehouseOperation.id)
        .join(ProductionItem, ProductionItem.id == WarehouseOperation.production_item_id)
        .join(CustomerOrderItem, CustomerOrderItem.id == ProductionItem.customer_order_item_id)
        .where(
            CustomerOrderItem.customer_order_id == customer_order_id,
            WarehouseOperation.source_type == "production_position",
            WarehouseOperation.status == WAREHOUSE_OPERATION_SUCCEEDED,
            WarehouseOperation.executed_at >= completed_at,
            ~select(reversal.id)
            .where(reversal.reversal_of_operation_id == WarehouseOperation.id)
            .exists(),
        )
        .limit(1)
    )
    if stored_id is not None:
        raise DomainError(
            "production_plan_position_stored",
            "生产计划完成后已经办理生产节点物料入库，不能恢复为生产中",
            status_code=409,
        )


__all__ = [
    "ensure_no_completed_plan_storage",
    "ensure_order_has_no_shipments",
    "reverse_plan_warehouse_issues",
]
