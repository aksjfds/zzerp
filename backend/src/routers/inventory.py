from fastapi import APIRouter, Depends, Query

from authorization import ensure_department_access, require_any_permission
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW
from modules.inventory.api import (
    issue_outbound_plan,
    list_outbound_plans,
    list_stocks,
    list_transactions,
)
from modules.inventory.finished_goods_api import (
    confirm_finished_order_receipt,
    list_finished_order_stocks,
    ship_finished_order_item,
)
from schemas.inventory import (
    InventoryIssueInput,
    InventoryOutboundPlanEnvelope,
    InventoryOutboundPlanResponse,
    InventoryStockEnvelope,
    InventoryTransactionEnvelope,
    FinishedOrderStockEnvelope,
    FinishedOrderStockItemEnvelope,
    FinishedShipmentInput,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/finished-order-stocks", response_model=FinishedOrderStockEnvelope)
def finished_order_stocks(
    operation: str = Query(default="all", pattern="^(all|receipt|shipment)$"),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return {"data": list_finished_order_stocks(operation)}


@router.post(
    "/finished-order-stocks/{customer_order_item_id}/receive",
    response_model=FinishedOrderStockItemEnvelope,
)
def finished_order_stock_receive(
    customer_order_item_id: int,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, "finished")
    return {"data": confirm_finished_order_receipt(customer_order_item_id, user["username"])}


@router.post(
    "/finished-order-stocks/{customer_order_item_id}/ship",
    response_model=FinishedOrderStockItemEnvelope,
)
def finished_order_stock_ship(
    customer_order_item_id: int,
    payload: FinishedShipmentInput,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, "finished")
    return {
        "data": ship_finished_order_item(
            customer_order_item_id,
            payload.quantity,
            user["username"],
        )
    }


@router.get("/outbound-plans", response_model=InventoryOutboundPlanEnvelope)
def inventory_outbound_plans(
    department_code: str = Query(pattern="^(warehouse|finished)$"),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    return {"data": list_outbound_plans(department_code)}


@router.post("/outbound-plans/{production_plan_id}/issue", response_model=InventoryOutboundPlanResponse)
def inventory_outbound_issue(
    production_plan_id: int,
    payload: InventoryIssueInput,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, payload.department_code)
    quantities = {item.reservation_id: item.quantity for item in payload.items}
    if len(quantities) != len(payload.items):
        from modules.errors import DomainError
        raise DomainError("duplicate_inventory_reservation", "出库项目不能重复", path="items")
    return issue_outbound_plan(
        production_plan_id,
        payload.department_code,
        quantities,
        user["username"],
    )


@router.get("/stocks", response_model=InventoryStockEnvelope)
def inventory_stocks(
    department_code: str = Query(pattern="^(warehouse|finished)$"),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    return {"data": list_stocks(department_code)}


@router.get("/transactions", response_model=InventoryTransactionEnvelope)
def inventory_transactions(
    department_code: str = Query(pattern="^(warehouse|finished)$"),
    stock_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=200, gt=0, le=1000),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    return {"data": list_transactions(department_code, stock_id, limit)}
