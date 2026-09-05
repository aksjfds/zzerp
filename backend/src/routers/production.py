from fastapi import APIRouter, Depends, Query, Response, status

from authorization import ensure_department_access, require_any_permission
from departments.contracts import (
    CAP_PRODUCTION_PROGRESS,
    CAP_PRODUCTION_WORKBENCH,
    CAP_WORKERS,
)
from departments.registry import department_api
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW, QC_INSPECT
from departments.warehouse_orchestration import (
    list_department_materials,
    store_production_position,
)
from schemas.production import (
    DepartmentMaterialPositionListEnvelope,
    DepartmentProductionProgressEnvelope,
    ProductionPositionStorageInput,
    ProductionPositionStorageResponse,
    DepartmentWorkerCreate,
    DepartmentWorkerUpdate,
    DepartmentWorkerEnvelope,
    DepartmentWorkerHistoryEnvelope,
    DepartmentWorkerOverviewEnvelope,
    DepartmentWorkerPayEnvelope,
    ProductionProgressItemDetailResponse,
    ProductionWorkbenchPositionListEnvelope,
    WorkerListEnvelope,
)


router = APIRouter(tags=["production"])


@router.get(
    "/departments/{department_code}/materials",
    response_model=DepartmentMaterialPositionListEnvelope,
)
def department_materials(
    department_code: str,
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    return {"data": list_department_materials(department_code)}


@router.post(
    "/departments/{department_code}/materials/storage",
    response_model=ProductionPositionStorageResponse,
)
def department_position_warehouse_storage(
    department_code: str,
    payload: ProductionPositionStorageInput,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, department_code)
    return store_production_position(
        department_code,
        payload.production_item_id,
        payload.processing_state_id,
        payload.flow_node_id,
        payload.source_flow_node_id,
        payload.position_version,
        payload.quantity,
        user["username"],
    )


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
    processing_workshop_id: int | None = Query(default=None, gt=0),
    flow_node_id: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    return department_api(
        department_code,
        CAP_PRODUCTION_PROGRESS,
    ).get_production_progress_item(
        production_plan_item_id,
        processing_workshop_id,
        flow_node_id,
    )


@router.get(
    "/departments/{department_code}/production-workbench/positions",
    response_model=ProductionWorkbenchPositionListEnvelope,
)
def department_production_workbench_positions(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    customer_order_item_id: int = Query(gt=0),
    workshop_id: int = Query(gt=0),
    flow_node_id: str = Query(min_length=1, max_length=200),
    production_item_id: int | None = Query(default=None, gt=0),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    ensure_department_access(user, department_code)
    data, total = department_api(
        department_code,
        CAP_PRODUCTION_WORKBENCH,
    ).list_production_workbench_positions(
        page,
        page_size,
        customer_order_item_id,
        workshop_id,
        flow_node_id,
        production_item_id,
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
    ensure_department_access(user, department_code)
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
    return {
        "data": department_api(
            department_code,
            CAP_WORKERS,
        ).worker_history(worker_id, month)
    }


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
    return {
        "data": department_api(
            department_code,
            CAP_WORKERS,
        ).worker_pay_summary(worker_id, month)
    }


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


@router.put(
    "/departments/{department_code}/workers/{worker_id}",
    response_model=DepartmentWorkerEnvelope,
)
def department_worker_update(
    department_code: str,
    worker_id: int,
    payload: DepartmentWorkerUpdate,
    user: dict = Depends(
        require_any_permission(PRODUCTION_MANAGE, QC_INSPECT, csrf=True)
    ),
):
    ensure_department_access(user, department_code)
    return {
        "data": department_api(department_code, CAP_WORKERS).update_worker(
            worker_id,
            payload.worker_name,
            payload.workshop_id,
        )
    }


@router.delete(
    "/departments/{department_code}/workers/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def department_worker_delete(
    department_code: str,
    worker_id: int,
    user: dict = Depends(
        require_any_permission(PRODUCTION_MANAGE, QC_INSPECT, csrf=True)
    ),
):
    ensure_department_access(user, department_code)
    department_api(department_code, CAP_WORKERS).delete_worker(worker_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
