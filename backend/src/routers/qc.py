from fastapi import APIRouter, Depends, Query

from authorization import ensure_department_access, require_any_permission
from domain.permissions import QC_INSPECT
from schemas.production import (
    PendingQcListEnvelope,
    QcDestinationInput,
    QcInspection,
    WorkOrderBatchEnvelope,
)
from departments.contracts import CAP_QUALITY
from departments.registry import department_api


router = APIRouter(prefix="/qc", tags=["qc"])
qc_department = department_api("qc", CAP_QUALITY)


@router.get("/work-order-batches", response_model=PendingQcListEnvelope)
def pending_qc_batches(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    production_item_id: int | None = Query(default=None, gt=0),
    history: bool = Query(default=False),
    keyword: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_any_permission(QC_INSPECT)),
):
    ensure_department_access(user, "qc")
    data, total = qc_department.list_qc_batches(
        page,
        page_size,
        production_item_id,
        history,
        keyword,
    )
    return {"data": data, "total": total}


@router.post(
    "/work-order-batches/{batch_id}/inspection",
    response_model=WorkOrderBatchEnvelope,
)
def qc_batch_inspect(
    batch_id: int,
    payload: QcInspection,
    user: dict = Depends(require_any_permission(QC_INSPECT, csrf=True)),
):
    ensure_department_access(user, "qc")
    return {
        "data": qc_department.inspect_qc_batch(
            batch_id,
            payload,
            user["department"],
            user["is_system"],
        )
    }


@router.post(
    "/work-order-batches/{batch_id}/destination",
    response_model=WorkOrderBatchEnvelope,
)
def qc_batch_destination(
    batch_id: int,
    payload: QcDestinationInput,
    user: dict = Depends(require_any_permission(QC_INSPECT, csrf=True)),
):
    ensure_department_access(user, "qc")
    return {
        "data": qc_department.decide_qc_destination(
            batch_id,
            payload,
            user["username"],
            user["department"],
            user["is_system"],
        )
    }
