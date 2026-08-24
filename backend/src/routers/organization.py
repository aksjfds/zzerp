from fastapi import APIRouter, Depends

from authorization import require_any_permission
from departments.registry import department_manifests
from domain.permissions import PRODUCT_VIEW
from modules.organization.api import (
    list_departments,
    list_procedures,
    list_workshops,
    list_workshop_routes,
)
from schemas.organization import (
    DepartmentModuleResponse,
    DepartmentResponse,
    ProcedureResponse,
    WorkshopResponse,
    WorkshopRouteResponse,
)


router = APIRouter(tags=["organization"])


@router.get("/department-modules", response_model=list[DepartmentModuleResponse])
def department_modules(
    _: dict = Depends(require_any_permission(PRODUCT_VIEW, "production:view")),
):
    return department_manifests()


@router.get("/departments", response_model=list[DepartmentResponse])
def departments(_: dict = Depends(require_any_permission(PRODUCT_VIEW, "order:view"))):
    return list_departments()


@router.get(
    "/departments/{department_id}/workshops", response_model=list[WorkshopResponse]
)
def workshops(
    department_id: int,
    _: dict = Depends(require_any_permission(PRODUCT_VIEW, "order:view")),
):
    return list_workshops(department_id)


@router.get("/procedures", response_model=list[ProcedureResponse])
def procedures(_: dict = Depends(require_any_permission(PRODUCT_VIEW))):
    return list_procedures()


@router.get("/workshop-routes", response_model=list[WorkshopRouteResponse])
def workshop_routes(_: dict = Depends(require_any_permission(PRODUCT_VIEW))):
    return list_workshop_routes()
