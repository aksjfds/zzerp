from fastapi import APIRouter, Depends, Query

from authorization import ensure_department_access, require_any_permission
from departments.finished_orchestration import list_finished_inbound_items
from departments.warehouse_orchestration import reverse_production_position_storage
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW
from domain.warehouse import WarehouseOperationStatus
from modules.inventory.api import (
    confirm_finished_receipt,
    list_finished_receipts,
    list_finished_shipment_candidates,
    list_finished_stock_reservations,
    list_finished_stock_transactions,
    list_finished_stocks,
    list_project_warehouse_operations,
    list_temporary_warehouse_stocks,
    review_project_warehouse_operation,
    reverse_finished_receipt,
    reverse_finished_shipment,
    ship_finished_order_item,
)
from schemas.inventory import (
    FinishedReceiptEnvelope,
    FinishedReceiptItemEnvelope,
    FinishedInboundItemEnvelope,
    FinishedStockEnvelope,
    FinishedStockReservationEnvelope,
    FinishedStockTransactionEnvelope,
    FinishedShipmentCandidateEnvelope,
    FinishedShipmentCandidateItemEnvelope,
    FinishedShipmentInput,
    OperationCorrectionInput,
    WarehouseOperationEnvelope,
    WarehouseOperationReviewInput,
    WarehouseOperationReversalInput,
    WarehouseStockEnvelope,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get(
    "/finished-inbound-items",
    response_model=FinishedInboundItemEnvelope,
)
def finished_inbound_items(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return list_finished_inbound_items(page, page_size)


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


@router.post(
    "/warehouse-operations/reverse-production-storage",
    response_model=WarehouseOperationEnvelope,
)
def warehouse_production_storage_reverse(
    payload: WarehouseOperationReversalInput,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, "warehouse")
    return {
        "data": reverse_production_position_storage(
            payload.operation_group_no,
            user["username"],
        )
    }


@router.get("/finished-receipts", response_model=FinishedReceiptEnvelope)
def finished_receipts(
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return {"data": list_finished_receipts()}


@router.post(
    "/finished-receipts/{receipt_id}/receive",
    response_model=FinishedReceiptItemEnvelope,
)
def finished_receipt_receive(
    receipt_id: int,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, "finished")
    return {"data": confirm_finished_receipt(receipt_id, user["username"])}


@router.post(
    "/finished-receipts/{receipt_id}/reverse",
    response_model=FinishedReceiptItemEnvelope,
)
def finished_receipt_reverse(
    receipt_id: int,
    payload: OperationCorrectionInput,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, "finished")
    return {"data": reverse_finished_receipt(receipt_id, user["username"], payload.reason)}


@router.get("/finished-shipments", response_model=FinishedShipmentCandidateEnvelope)
def finished_shipment_candidates(
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return {"data": list_finished_shipment_candidates()}


@router.post(
    "/finished-shipments/{customer_order_item_id}",
    response_model=FinishedShipmentCandidateItemEnvelope,
)
def finished_shipment_confirm(
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


@router.post(
    "/finished-shipment-transactions/{transaction_id}/reverse",
    response_model=FinishedShipmentCandidateItemEnvelope,
)
def finished_shipment_reverse(
    transaction_id: int,
    payload: OperationCorrectionInput,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, "finished")
    return {
        "data": reverse_finished_shipment(
            transaction_id,
            user["username"],
            payload.reason,
        )
    }


@router.get("/finished-stocks", response_model=FinishedStockEnvelope)
def finished_stocks(
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return {"data": list_finished_stocks()}


@router.get(
    "/finished-reservations",
    response_model=FinishedStockReservationEnvelope,
)
def finished_stock_reservations(
    production_plan_id: int | None = Query(default=None, gt=0),
    customer_order_item_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=200, gt=0, le=1000),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return {
        "data": list_finished_stock_reservations(
            production_plan_id=production_plan_id,
            customer_order_item_id=customer_order_item_id,
            limit=limit,
        )
    }


@router.get("/finished-transactions", response_model=FinishedStockTransactionEnvelope)
def finished_stock_transactions(
    finished_stock_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=200, gt=0, le=1000),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, "finished")
    return {
        "data": list_finished_stock_transactions(
            finished_stock_id=finished_stock_id,
            limit=limit,
        )
    }
