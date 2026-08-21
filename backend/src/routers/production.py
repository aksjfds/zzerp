from fastapi import APIRouter, Depends, HTTPException, Query

from authorization import ensure_department_access, require_any_permission
from departments.contracts import (
    CAP_PRODUCTION_PROGRESS,
    CAP_REPOSITORIES,
    CAP_WORKERS,
)
from departments.registry import department_api
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW, QC_INSPECT
from modules.organization.api import list_workshops_by_department_code
from schemas.production import (
    DepartmentProductionProgressEnvelope,
    DepartmentSurplusInventoryEnvelope,
    DepartmentWorkerCreate,
    DepartmentWorkerEnvelope,
    DepartmentWorkerHistoryEnvelope,
    DepartmentWorkerOverviewEnvelope,
    DepartmentWorkerPayEnvelope,
    RepositoryListEnvelope,
    ProductionProgressItemDetailResponse,
    WarehouseStorageInput,
    WarehouseStorageResponse,
    WorkerListEnvelope,
)
from schemas.organization import WorkshopResponse


router = APIRouter(tags=["production"])


@router.get(
    "/departments/{department_code}/surplus-inventory",
    response_model=DepartmentSurplusInventoryEnvelope,
)
def department_surplus_inventory(
    department_code: str,
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    if department_code == "qc":
        return {"data": []}
    from modules.production_core.warehouse_storage import list_closed_surplus_positions
    return {"data": list_closed_surplus_positions(department_code)}


@router.post(
    "/departments/{department_code}/warehouse-storage",
    response_model=WarehouseStorageResponse,
)
def department_warehouse_storage(
    department_code: str,
    payload: WarehouseStorageInput,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, department_code)
    from modules.production_core.warehouse_storage import store_position_in_warehouse
    return store_position_in_warehouse(
        department_code,
        payload.production_item_id,
        payload.flow_node_id,
        payload.source_flow_node_id,
        payload.quantity,
        user["username"],
    )


@router.get(
    "/departments/{department_code}/repository-workshops",
    response_model=list[WorkshopResponse],
)
def department_repository_workshops(
    department_code: str,
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    return list_workshops_by_department_code(department_code)


@router.get(
    "/departments/{department_code}/production-progress",
    response_model=DepartmentProductionProgressEnvelope,
)
def department_production_progress(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    keyword: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    data, total = department_api(
        department_code,
        CAP_PRODUCTION_PROGRESS,
    ).list_production_progress(page, page_size, keyword)
    return {"data": data, "total": total}


@router.get(
    "/departments/{department_code}/production-progress/items/"
    "{production_plan_item_id}",
    response_model=ProductionProgressItemDetailResponse,
)
def department_production_progress_item(
    department_code: str,
    production_plan_item_id: int,
    processing_workshop: str | None = Query(default=None, max_length=100),
    flow_node_id: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    return department_api(
        department_code,
        CAP_PRODUCTION_PROGRESS,
    ).get_production_progress_item(
        production_plan_item_id,
        processing_workshop,
        flow_node_id,
    )


@router.get(
    "/departments/{department_code}/repositories",
    response_model=RepositoryListEnvelope,
)
def department_repositories(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=10000),
    keyword: str | None = Query(default=None, max_length=200),
    workshop_name: str | None = Query(default=None, max_length=200),
    work_status: str = Query(
        default="all",
        pattern=(
            "^(all|unprocessed|processing|processing_completed|qc|rework|completed)$"
        ),
    ),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    data, total = department_api(
        department_code,
        CAP_REPOSITORIES,
    ).list_repositories(
        page,
        page_size,
        keyword,
        workshop_name,
        work_status,
    )
    return {"data": data, "total": total}


@router.get(
    "/departments/{department_code}/workers",
    response_model=WorkerListEnvelope,
)
def department_workers(
    department_code: str,
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    return {
        "data": department_api(
            department_code,
            CAP_WORKERS,
        ).list_workers()
    }


@router.get(
    "/departments/{department_code}/worker-overview",
    response_model=DepartmentWorkerOverviewEnvelope,
)
def department_worker_overview_get(
    department_code: str,
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    return {
        "data": department_api(
            department_code,
            CAP_WORKERS,
        ).worker_overview()
    }


@router.get(
    "/departments/{department_code}/workers/{worker_id}/work-history",
    response_model=DepartmentWorkerHistoryEnvelope,
)
def department_worker_history_get(
    department_code: str,
    worker_id: int,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    try:
        data = department_api(
            department_code,
            CAP_WORKERS,
        ).worker_history(worker_id, month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"data": data}


@router.get(
    "/departments/{department_code}/workers/{worker_id}/pay",
    response_model=DepartmentWorkerPayEnvelope,
)
def department_worker_pay_get(
    department_code: str,
    worker_id: int,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    try:
        data = department_api(
            department_code,
            CAP_WORKERS,
        ).worker_pay_summary(worker_id, month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"data": data}


@router.post(
    "/departments/{department_code}/workers",
    response_model=DepartmentWorkerEnvelope,
)
def department_worker_create(
    department_code: str,
    payload: DepartmentWorkerCreate,
    user: dict = Depends(
        require_any_permission(PRODUCTION_MANAGE, QC_INSPECT, csrf=True)
    ),
):
    ensure_department_access(user, department_code)
    return {
        "data": department_api(
            department_code,
            CAP_WORKERS,
        ).create_worker(
            payload.worker_name,
            payload.workshop_id,
        )
    }
