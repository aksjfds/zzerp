"""Inventory allocation for a locked draft production plan."""

from sqlalchemy.orm import Session

from domain.production_inventory import IssuedInventoryStock, IssuedPlanItem
from domain.warehouse import (
    WAREHOUSE_OPERATION_SUCCEEDED,
    WAREHOUSE_SOURCE_PLAN_CONFIRMATION,
    WarehouseOperationContext,
)
from modules.errors import DomainError
from modules.inventory.warehouse_api import WarehouseOutboundRequest
from modules.planning.execution_contract import PlanExecutionCollaborators
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.plan_stock_view import (
    completion_status_priority,
    processing_state_by_status,
)


def allocate_plan_inventory(
    session: Session,
    plan: ProductionPlan,
    actor_username: str,
    collaborators: PlanExecutionCollaborators,
) -> tuple[tuple[IssuedPlanItem, IssuedInventoryStock], ...]:
    issued_rows: list[tuple[IssuedPlanItem, IssuedInventoryStock]] = []
    flow_cache: dict = {}
    for item in plan.items:
        quantity = item.estimated_inventory_quantity
        if quantity <= 0:
            continue
        plan_item = _issued_plan_item(item)
        if item.item_type == "finished_product":
            allocated = collaborators.reserve_finished_plan_stock(
                session,
                production_plan_id=plan.id,
                plan_item=plan_item,
                requested_quantity=quantity,
            )
            stocks = ()
        else:
            stocks = _withdraw_material_stock(
                session,
                plan,
                item,
                plan_item,
                quantity,
                actor_username,
                collaborators,
                flow_cache,
            )
            allocated = sum(stock.quantity for stock in stocks)
        if allocated != quantity:
            raise DomainError(
                "production_plan_inventory_allocation_invalid",
                "库存分配结果与生产计划不一致",
                status_code=409,
            )
        item.allocated_inventory_quantity += allocated
        issued_rows.extend((plan_item, stock) for stock in stocks)
    return tuple(issued_rows)


def _withdraw_material_stock(
    session: Session,
    plan: ProductionPlan,
    item: ProductionPlanItem,
    plan_item: IssuedPlanItem,
    quantity: int,
    actor_username: str,
    collaborators: PlanExecutionCollaborators,
    flow_cache: dict,
) -> tuple[IssuedInventoryStock, ...]:
    priority = completion_status_priority(session, item, flow_cache)
    states = processing_state_by_status(session, item, flow_cache)
    if not priority:
        raise DomainError(
            "production_plan_inventory_state_missing",
            "可用仓库库存缺少本产品版本的加工状态记录",
            status_code=409,
            path="items",
        )
    result = collaborators.withdraw_warehouse_stock(
        session,
        WarehouseOutboundRequest(
            operation_group_no=(
                f"plan:{plan.id}:item:{item.id}:confirm:revision:{plan.revision}"
            ),
            context=WarehouseOperationContext(
                source_type=WAREHOUSE_SOURCE_PLAN_CONFIRMATION,
                production_plan_id=plan.id,
                production_plan_item_id=item.id,
            ),
            item_code=item.item_code,
            item_name=item.item_name,
            product_version=item.product_version,
            item_type=item.item_type,
            completion_status_priority=priority,
            processing_state_ids=tuple((status, states[status].id) for status in priority),
            quantity=quantity,
            actor_username=actor_username,
        ),
    )
    if result.status != WAREHOUSE_OPERATION_SUCCEEDED:
        raise DomainError(
            "production_plan_inventory_changed",
            result.error_message or "仓库库存已变化，请重新加载生产计划",
            status_code=409,
            path="items",
        )
    stocks: list[IssuedInventoryStock] = []
    for operation in result.operations:
        state = states.get(operation.completion_status)
        if (
            state is None
            or operation.processing_state_id != state.id
            or operation.warehouse_stock_id is None
            or operation.quantity_before is None
            or operation.quantity_after is None
        ):
            raise DomainError(
                "production_plan_inventory_result_invalid",
                "仓库扣减结果无法对应订单绑定版本的正式流程",
                status_code=409,
            )
        stocks.append(IssuedInventoryStock(
            production_plan_item_id=plan_item.id,
            stock_id=operation.warehouse_stock_id,
            product_id=plan_item.product_id,
            product_version=plan_item.product_version,
            flow_node_id=plan_item.flow_node_id,
            processing_state_id=state.id,
            resume_flow_node_id=state.resume_flow_node_id,
            quantity=operation.quantity,
            quantity_before=operation.quantity_before,
            quantity_after=operation.quantity_after,
        ))
    return tuple(stocks)


def _issued_plan_item(item: ProductionPlanItem) -> IssuedPlanItem:
    return IssuedPlanItem(
        id=item.id,
        customer_order_item_id=item.customer_order_item_id,
        product_id=item.product_id,
        product_version=item.product_version,
        item_type=item.item_type,
        product_bom_id=item.product_bom_id,
        flow_node_id=item.flow_node_id,
    )


__all__ = ["allocate_plan_inventory"]
