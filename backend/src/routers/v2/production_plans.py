from fastapi import APIRouter, Depends, HTTPException

from domain.enums import ProductionPlanStatus
from schemas.planning import (
    ProductionPlanCreate,
    ProductionPlanData,
    ProductionPlanItemsInput,
    ProductionPlanPreviewData,
    ProductionPlanPreviewInput,
    ProductionPlanUpdate,
)
from security import require_any_permission
from services.production_plans import ProductionPlanService

router = APIRouter(prefix="/v2/production-plans", tags=["v2-production-plans"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[ProductionPlanData])
def list_plans(
    status: ProductionPlanStatus | None = None,
    _: dict = Depends(
        require_any_permission("plan:view", "plan:edit", "plan:manage")
    ),
):
    return ProductionPlanService.list_plans(
        status.value if status is not None else None
    )


@router.post("/preview", response_model=ProductionPlanPreviewData)
def preview_plan(
    payload: ProductionPlanPreviewInput,
    _: dict = Depends(
        require_any_permission("plan:edit", "plan:manage", csrf=True)
    ),
):
    try:
        return ProductionPlanService.preview(payload.customer_order_id, payload.items)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("", response_model=ProductionPlanData)
def create_plan(
    payload: ProductionPlanCreate,
    user: dict = Depends(
        require_any_permission("plan:edit", "plan:manage", csrf=True)
    ),
):
    try:
        return ProductionPlanService.create_plan(payload, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{plan_id}/preview", response_model=ProductionPlanPreviewData)
def preview_plan_update(
    plan_id: int,
    payload: ProductionPlanItemsInput,
    _: dict = Depends(
        require_any_permission("plan:edit", "plan:manage", csrf=True)
    ),
):
    try:
        return ProductionPlanService.preview_update(plan_id, payload.items)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.put("/{plan_id}", response_model=ProductionPlanData)
def update_plan(
    plan_id: int,
    payload: ProductionPlanUpdate,
    user: dict = Depends(
        require_any_permission("plan:edit", "plan:manage", csrf=True)
    ),
):
    try:
        return ProductionPlanService.update_plan(plan_id, payload, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{plan_id}/release", response_model=ProductionPlanData)
def release_plan(
    plan_id: int,
    user: dict = Depends(
        require_any_permission("plan:edit", "plan:manage", csrf=True)
    ),
):
    try:
        return ProductionPlanService.release_plan(plan_id, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/{plan_id}/cancel", response_model=ProductionPlanData)
def cancel_plan(
    plan_id: int,
    user: dict = Depends(
        require_any_permission("plan:edit", "plan:manage", csrf=True)
    ),
):
    try:
        return ProductionPlanService.cancel_plan(plan_id, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc
