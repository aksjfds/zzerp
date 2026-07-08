from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from authorization import require_any_permission
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW, QC_INSPECT
from schemas.production import (
    PendingQcListEnvelope,
    AssemblyWorkOrderCreate,
    QcInspection,
    RepositoryListEnvelope,
    WorkOrderCreate,
    WorkOrderEnvelope,
    WorkOrderListEnvelope,
    WorkOrderSubmission,
    WorkOrderBatchEnvelope,
    WorkerListEnvelope,
)
from services.production_cards import list_production_cards
from services.work_orders import (
    create_work_order,
    create_assembly_work_order,
    cancel_work_order,
    inspect_batch,
    list_department_work_orders,
    list_department_workers,
    list_qc_batches,
    submit_work_order,
)


router = APIRouter(tags=["production"])


@router.get(
    "/departments/{department_code}/repositories",
    response_model=RepositoryListEnvelope,
)
def department_repositories(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=10000),
    keyword: str | None = Query(default=None, max_length=200),
    arrived_from: date | None = None,
    arrived_to: date | None = None,
    work_status: str = Query(default="all", pattern="^(all|unprocessed|processing|completed)$"),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    if arrived_from and arrived_to and arrived_from > arrived_to:
        raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
    data, total = list_production_cards(
        department_code, page, page_size, keyword, arrived_from, arrived_to, work_status
    )
    return {"data": data, "total": total}


@router.get(
    "/departments/{department_code}/work-orders",
    response_model=WorkOrderListEnvelope,
)
def department_work_orders(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    production_item_id: int | None = Query(default=None, gt=0),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    data, total = list_department_work_orders(
        department_code, page, page_size, production_item_id
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
    return {"data": list_department_workers(department_code)}


@router.post("/work-orders", response_model=WorkOrderEnvelope)
def work_order_create(
    payload: WorkOrderCreate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": create_work_order(
            payload.repository_id,
            payload.quantity,
            payload.worker_id,
            user["department"],
        )
    }


@router.post("/assembly-work-orders", response_model=WorkOrderEnvelope)
def assembly_work_order_create(
    payload: AssemblyWorkOrderCreate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": create_assembly_work_order(
            payload.repository_ids,
            payload.quantity,
            payload.worker_id,
            user["department"],
        )
    }


@router.post("/work-orders/{work_order_id}/submissions", response_model=WorkOrderEnvelope)
def work_order_submit(
    work_order_id: int,
    payload: WorkOrderSubmission,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {"data": submit_work_order(work_order_id, payload.quantity, user["department"])}


@router.post("/work-orders/{work_order_id}/cancel", response_model=WorkOrderEnvelope)
def work_order_cancel(
    work_order_id: int,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {"data": cancel_work_order(work_order_id, user["department"])}


@router.get("/qc/work-order-batches", response_model=PendingQcListEnvelope)
def pending_qc_batches(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    production_item_id: int | None = Query(default=None, gt=0),
    user: dict = Depends(require_any_permission(QC_INSPECT)),
):
    if user["department"] not in {"sys", "qc"}:
        raise HTTPException(status_code=403, detail="只有 QC 可以查看质检批次")
    data, total = list_qc_batches(page, page_size, production_item_id)
    return {"data": data, "total": total}


@router.post(
    "/qc/work-order-batches/{batch_id}/inspection",
    response_model=WorkOrderBatchEnvelope,
)
def qc_batch_inspect(
    batch_id: int,
    payload: QcInspection,
    user: dict = Depends(require_any_permission(QC_INSPECT, csrf=True)),
):
    return {
        "data": inspect_batch(
            batch_id,
            payload,
            user["department"],
        )
    }
