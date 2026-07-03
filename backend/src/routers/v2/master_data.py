from fastapi import APIRouter, Depends, HTTPException

from schemas.catalog import (
    SurfaceTreatmentCreate,
    SurfaceTreatmentSummary,
    SurfaceTreatmentUpdate,
)
from schemas.organization import (
    DepartmentSummary,
    WorkshopCreate,
    WorkshopSummary,
    WorkshopUpdate,
)
from security import require_any_permission
from services.master_data import MasterDataService

router = APIRouter(prefix="/v2/master-data", tags=["v2-master-data"])


@router.get("/departments", response_model=list[DepartmentSummary])
def list_departments(
    _: dict = Depends(
        require_any_permission("master:manage", "product:view", "route:edit")
    ),
):
    return MasterDataService.list_departments()


@router.get("/workshops", response_model=list[WorkshopSummary])
def list_workshops(
    department_id: int | None = None,
    _: dict = Depends(
        require_any_permission("master:manage", "product:view", "route:edit")
    ),
):
    return MasterDataService.list_workshops(department_id)


@router.post("/workshops", response_model=WorkshopSummary)
def create_workshop(
    payload: WorkshopCreate,
    _: dict = Depends(require_any_permission("master:manage", csrf=True)),
):
    try:
        return MasterDataService.create_workshop(
            department_id=payload.department_id,
            workshop_code=payload.workshop_code,
            workshop_name=payload.workshop_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/workshops/{workshop_id}", response_model=WorkshopSummary)
def update_workshop(
    workshop_id: int,
    payload: WorkshopUpdate,
    _: dict = Depends(require_any_permission("master:manage", csrf=True)),
):
    try:
        return MasterDataService.update_workshop(
            workshop_id=workshop_id,
            workshop_name=payload.workshop_name,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/surface-treatments",
    response_model=list[SurfaceTreatmentSummary],
)
def list_surface_treatments(
    customer_name: str | None = None,
    _: dict = Depends(
        require_any_permission("master:manage", "product:view", "product:edit")
    ),
):
    return MasterDataService.list_surface_treatments(customer_name)


@router.post("/surface-treatments", response_model=SurfaceTreatmentSummary)
def create_surface_treatment(
    payload: SurfaceTreatmentCreate,
    _: dict = Depends(
        require_any_permission("master:manage", "product:edit", csrf=True)
    ),
):
    try:
        return MasterDataService.create_surface_treatment(
            customer_name=payload.customer_name,
            treatment_name=payload.treatment_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/surface-treatments/{treatment_id}",
    response_model=SurfaceTreatmentSummary,
)
def update_surface_treatment(
    treatment_id: int,
    payload: SurfaceTreatmentUpdate,
    _: dict = Depends(
        require_any_permission("master:manage", "product:edit", csrf=True)
    ),
):
    try:
        return MasterDataService.update_surface_treatment(
            treatment_id=treatment_id,
            treatment_name=payload.treatment_name,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
