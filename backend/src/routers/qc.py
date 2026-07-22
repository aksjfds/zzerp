from fastapi import APIRouter, Depends, HTTPException, Query

from authorization import require_any_permission
from domain.permissions import QC_INSPECT
from schemas.production import (
    PendingQcListEnvelope,
    QcDispatchCreate,
    QcDispatchEnvelope,
    QcInspection,
    WorkOrderBatchEnvelope,
)
from services.qc_inspections import inspect_batch
from services.qc_dispatches import dispatch_qc_batch
from services.work_order_queries import list_qc_batches


router = APIRouter(prefix="/qc", tags=["qc"])


@router.get("/work-order-batches", response_model=PendingQcListEnvelope)
def pending_qc_batches(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    production_item_id: int | None = Query(default=None, gt=0),
    history: bool = Query(default=False),
    keyword: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_any_permission(QC_INSPECT)),
):
    if user["department"] not in {"sys", "qc"}:
        raise HTTPException(status_code=403, detail="只有 QC 可以查看质检批次")
    data, total = list_qc_batches(
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
    return {"data": inspect_batch(batch_id, payload, user["department"])}


@router.post(
    "/work-order-batches/{batch_id}/dispatch",
    response_model=QcDispatchEnvelope,
)
def qc_batch_dispatch(
    batch_id: int,
    payload: QcDispatchCreate,
    user: dict = Depends(require_any_permission(QC_INSPECT, csrf=True)),
):
    return {
        "data": dispatch_qc_batch(batch_id, payload.quantity, user["department"])
    }
