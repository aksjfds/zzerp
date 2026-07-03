from fastapi import APIRouter, Depends, HTTPException

from domain.enums import CustomerOrderStatus
from schemas.sales import CustomerOrderCreate, CustomerOrderData, CustomerOrderUpdate
from security import require_any_permission
from services.customer_orders import CustomerOrderService

router = APIRouter(prefix="/v2/customer-orders", tags=["v2-customer-orders"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[CustomerOrderData])
def list_orders(
    keyword: str | None = None,
    status: CustomerOrderStatus | None = None,
    _: dict = Depends(
        require_any_permission("order:view", "order:edit", "order:manage")
    ),
):
    return CustomerOrderService.list_orders(
        keyword,
        status.value if status is not None else None,
    )


@router.get("/{order_id}", response_model=CustomerOrderData)
def get_order(
    order_id: int,
    _: dict = Depends(
        require_any_permission("order:view", "order:edit", "order:manage")
    ),
):
    try:
        return CustomerOrderService.get_order(order_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("", response_model=CustomerOrderData)
def create_order(
    payload: CustomerOrderCreate,
    user: dict = Depends(
        require_any_permission("order:edit", "order:manage", csrf=True)
    ),
):
    try:
        return CustomerOrderService.create_order(payload, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.put("/{order_id}", response_model=CustomerOrderData)
def update_order(
    order_id: int,
    payload: CustomerOrderUpdate,
    _: dict = Depends(
        require_any_permission("order:edit", "order:manage", csrf=True)
    ),
):
    try:
        return CustomerOrderService.update_order(order_id, payload)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{order_id}/confirm", response_model=CustomerOrderData)
def confirm_order(
    order_id: int,
    user: dict = Depends(
        require_any_permission("order:edit", "order:manage", csrf=True)
    ),
):
    try:
        return CustomerOrderService.confirm_order(order_id, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{order_id}/changes", response_model=CustomerOrderData)
def create_order_change(
    order_id: int,
    user: dict = Depends(
        require_any_permission("order:edit", "order:manage", csrf=True)
    ),
):
    try:
        return CustomerOrderService.create_change(order_id, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{order_id}/cancel", response_model=CustomerOrderData)
def cancel_order(
    order_id: int,
    _: dict = Depends(
        require_any_permission("order:edit", "order:manage", csrf=True)
    ),
):
    try:
        return CustomerOrderService.cancel_order(order_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
