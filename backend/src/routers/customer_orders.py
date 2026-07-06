from fastapi import APIRouter, Depends, Response, status

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


router = APIRouter(prefix="/customer-orders", tags=["customer-orders"])


@router.get("", response_model=CustomerOrderListEnvelope)
def customer_order_list(_: dict = Depends(require_any_permission(ORDER_VIEW))):
    return {"data": list_orders()}


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
    _: dict = Depends(require_any_permission(ORDER_CONFIRM, csrf=True)),
):
    return {"data": change_status(order_id, "confirmed")}


@router.post("/{order_id}/cancel", response_model=CustomerOrderEnvelope)
def customer_order_cancel(
    order_id: int,
    _: dict = Depends(require_any_permission(ORDER_CANCEL, csrf=True)),
):
    return {"data": change_status(order_id, "cancelled")}


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def customer_order_delete(
    order_id: int,
    _: dict = Depends(require_any_permission(ORDER_EDIT, csrf=True)),
):
    delete_order(order_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
