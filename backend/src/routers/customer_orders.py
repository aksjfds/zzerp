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
    ProductionPlanEnvelope,
    ProductionPlanUpdate,
)
from modules.sales.api import (
    change_status,
    confirm_production_plan,
    create_order,
    delete_order,
    get_customer_order_production,
    get_order,
    list_orders,
    update_order,
)
from modules.planning.api import get_order_plan, update_order_plan


router = APIRouter(prefix="/customer-orders", tags=["customer-orders"])


@router.get("", response_model=CustomerOrderListEnvelope)
def customer_order_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    include_progress: bool = Query(default=False),
    _: dict = Depends(require_any_permission(ORDER_VIEW)),
):
    data, total = list_orders(page, page_size, include_progress=include_progress)
    return {"data": data, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CustomerOrderEnvelope)
def customer_order_create(
    payload: CustomerOrderCreate,
    _: dict = Depends(require_any_permission(ORDER_ADD, csrf=True)),
):
    return {"data": create_order(payload)}


@router.get("/production-plans", response_model=CustomerOrderListEnvelope)
def production_plan_order_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    _: dict = Depends(require_any_permission(ORDER_VIEW)),
):
    data, total = list_orders(
        page,
        page_size,
        statuses={"confirmed", "planned", "closed"},
    )
    return {"data": data, "total": total}


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


@router.get("/{order_id}/production-plan", response_model=ProductionPlanEnvelope)
def customer_order_production_plan(
    order_id: int,
    _: dict = Depends(require_any_permission(ORDER_VIEW)),
):
    return {"data": get_order_plan(order_id)}


@router.put("/{order_id}/production-plan", response_model=ProductionPlanEnvelope)
def customer_order_production_plan_update(
    order_id: int,
    payload: ProductionPlanUpdate,
    _: dict = Depends(require_any_permission(ORDER_EDIT, csrf=True)),
):
    quantities = {item.id: item.planned_production_quantity for item in payload.items}
    if len(quantities) != len(payload.items):
        from modules.errors import DomainError
        raise DomainError("duplicate_production_plan_item", "生产计划项目不能重复", path="items")
    return {
        "data": update_order_plan(order_id, payload.expected_revision, quantities)
    }


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
    user: dict = Depends(require_any_permission(ORDER_CONFIRM, csrf=True)),
):
    return {
        "data": change_status(
            order_id,
            "confirmed",
            expected_revision,
            actor_username=user["username"],
        )
    }


@router.post("/{order_id}/production-plan/confirm", response_model=CustomerOrderEnvelope)
def customer_order_production_plan_confirm(
    order_id: int,
    expected_revision: int = Query(gt=0),
    plan_expected_revision: int = Query(gt=0),
    user: dict = Depends(require_any_permission(ORDER_CONFIRM, csrf=True)),
):
    return {
        "data": confirm_production_plan(
            order_id,
            expected_revision,
            plan_expected_revision,
            actor_username=user["username"],
        )
    }


@router.post("/{order_id}/cancel", response_model=CustomerOrderEnvelope)
def customer_order_cancel(
    order_id: int,
    expected_revision: int = Query(gt=0),
    user: dict = Depends(require_any_permission(ORDER_CANCEL, csrf=True)),
):
    return {
        "data": change_status(
            order_id,
            "cancelled",
            expected_revision,
            actor_username=user["username"],
        )
    }


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def customer_order_delete(
    order_id: int,
    expected_revision: int = Query(gt=0),
    _: dict = Depends(require_any_permission(ORDER_EDIT, csrf=True)),
):
    delete_order(order_id, expected_revision)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
