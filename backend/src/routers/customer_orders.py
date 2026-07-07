from fastapi import APIRouter, Depends, Query, Response, status

from authorization import require_any_permission
from domain.permissions import (
    ORDER_ADD,
    ORDER_CANCEL,
    ORDER_CONFIRM,
    ORDER_EDIT,
    ORDER_VIEW,
)
from schemas.sales import (
    CustomerOrderCreate,
    CustomerOrderEnvelope,
    CustomerOrderListEnvelope,
    CustomerOrderUpdate,
)
from services.customer_orders import (
    change_status,
    create_order,
    delete_order,
    get_order,
    list_orders,
    update_order,
)
from services.customer_order_production import get_customer_order_production


router = APIRouter(prefix="/customer-orders", tags=["customer-orders"])


@router.get("", response_model=CustomerOrderListEnvelope)
def customer_order_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    _: dict = Depends(require_any_permission(ORDER_VIEW)),
):
    data, total = list_orders(page, page_size)
    return {"data": data, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CustomerOrderEnvelope)
def customer_order_create(
    payload: CustomerOrderCreate,
    _: dict = Depends(require_any_permission(ORDER_ADD, csrf=True)),
):
    return {"data": create_order(payload)}


@router.get("/{order_id}", response_model=CustomerOrderEnvelope)
def customer_order_detail(
    order_id: int,
    _: dict = Depends(require_any_permission(ORDER_VIEW)),
):
    return {"data": get_order(order_id)}


@router.get("/{order_id}/production-status")
def customer_order_production_status(
    order_id: int,
    _: dict = Depends(require_any_permission(ORDER_VIEW)),
):
    return {"data": get_customer_order_production(order_id)}


@router.put("/{order_id}", response_model=CustomerOrderEnvelope)
def customer_order_update(
    order_id: int,
    payload: CustomerOrderUpdate,
    _: dict = Depends(require_any_permission(ORDER_EDIT, csrf=True)),
):
    return {"data": update_order(order_id, payload)}


@router.post("/{order_id}/confirm", response_model=CustomerOrderEnvelope)
def customer_order_confirm(
    order_id: int,
    expected_revision: int = Query(gt=0),
    _: dict = Depends(require_any_permission(ORDER_CONFIRM, csrf=True)),
):
    return {"data": change_status(order_id, "confirmed", expected_revision)}


@router.post("/{order_id}/cancel", response_model=CustomerOrderEnvelope)
def customer_order_cancel(
    order_id: int,
    expected_revision: int = Query(gt=0),
    _: dict = Depends(require_any_permission(ORDER_CANCEL, csrf=True)),
):
    return {"data": change_status(order_id, "cancelled", expected_revision)}


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def customer_order_delete(
    order_id: int,
    expected_revision: int = Query(gt=0),
    _: dict = Depends(require_any_permission(ORDER_EDIT, csrf=True)),
):
    delete_order(order_id, expected_revision)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
