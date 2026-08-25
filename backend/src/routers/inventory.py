from typing import Literal

from fastapi import APIRouter, Depends, Query

from authorization import ensure_department_access, require_any_permission
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW
from domain.warehouse import WarehouseOperationStatus
from modules.inventory.api import (
    confirm_finished_order_receipt,
    list_finished_order_stocks,
    list_project_warehouse_operations,
    list_finished_inventory_stocks,
    list_temporary_warehouse_stocks,
    list_finished_inventory_transactions,
    review_project_warehouse_operation,
    ship_finished_order_item,
)
from schemas.inventory import (
    FinishedInventoryStockEnvelope,
    FinishedInventoryTransactionEnvelope,
    FinishedOrderStockEnvelope,
    FinishedOrderStockItemEnvelope,
    FinishedShipmentInput,
    WarehouseOperationEnvelope,
    WarehouseOperationReviewInput,
    WarehouseStockEnvelope,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/warehouse-stocks", response_model=WarehouseStockEnvelope)
def warehouse_stocks(
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "warehouse")
    return {"data": list_temporary_warehouse_stocks()}


@router.get("/warehouse-operations", response_model=WarehouseOperationEnvelope)
def warehouse_operations(
    status: WarehouseOperationStatus | None = Query(default=None),
    limit: int = Query(default=200, gt=0, le=1000),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "warehouse")
    return {"data": list_project_warehouse_operations(status, limit)}


@router.post(
    "/warehouse-operations/review",
    response_model=WarehouseOperationEnvelope,
)
def warehouse_operation_review(
    payload: WarehouseOperationReviewInput,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, "warehouse")
    return {
        "data": review_project_warehouse_operation(
            payload.operation_group_no,
            user["username"],
            payload.review_note,
        )
    }


@router.get("/finished-order-stocks", response_model=FinishedOrderStockEnvelope)
def finished_order_stocks(
    operation: Literal["all", "receipt", "shipment"] = Query(default="all"),
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


@router.get("/finished-stocks", response_model=FinishedInventoryStockEnvelope)
def finished_inventory_stocks(
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return {"data": list_finished_inventory_stocks()}


@router.get("/finished-transactions", response_model=FinishedInventoryTransactionEnvelope)
def finished_inventory_transactions(
    stock_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=200, gt=0, le=1000),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return {"data": list_finished_inventory_transactions(stock_id, limit)}
