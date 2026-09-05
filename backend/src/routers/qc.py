from fastapi import APIRouter, Depends, Query, Response, status

from authorization import ensure_department_access, require_any_permission
from domain.permissions import QC_INSPECT
from schemas.production import (
    QcInspectionBatchListEnvelope,
    QcDestinationInput,
    QcInspection,
    ProductionProgressWorkOrderResponse,
    WorkOrderBatchEnvelope,
    WorkOrderEnvelope,
)
from modules.supplier_processing.api import (
    list_qc_tasks as list_supplier_processing_qc_tasks,
    record_supplier_processing_inspection,
    release_supplier_processing_batch,
)
from schemas.supplier_processing import (
    SupplierProcessingQcInspection,
    SupplierProcessingQcTaskListEnvelope,
)
from departments.contracts import CAP_QUALITY
from departments.registry import department_api


router = APIRouter(prefix="/qc", tags=["qc"])
qc_department = department_api("qc", CAP_QUALITY)


@router.get(
    "/supplier-processing-work-orders",
    response_model=SupplierProcessingQcTaskListEnvelope,
)
def supplier_processing_qc_tasks(
    history: bool = Query(default=False),
    user: dict = Depends(require_any_permission(QC_INSPECT)),
):
    ensure_department_access(user, "qc")
    data, total = list_supplier_processing_qc_tasks(history=history)
    return {"data": data, "total": total}


@router.post(
    "/supplier-processing-work-orders/{work_order_id}/inspections",
    response_model=WorkOrderBatchEnvelope,
)
def supplier_processing_qc_inspect(
    work_order_id: int,
    payload: SupplierProcessingQcInspection,
    user: dict = Depends(require_any_permission(QC_INSPECT, csrf=True)),
):
    ensure_department_access(user, "qc")
    return {
        "data": record_supplier_processing_inspection(
            work_order_id=work_order_id,
            qc_worker_id=payload.qc_worker_id,
            qualified_quantity=payload.qualified_quantity,
            rework_quantity=payload.rework_quantity,
            scrap_quantity=payload.scrap_quantity,
            lost_quantity=payload.lost_quantity,
            defect_reason=payload.defect_reason,
            actor_department=user["department"],
            actor_is_system=user["is_system"],
        )
    }


@router.post(
    "/supplier-processing-batches/{batch_id}/release",
    response_model=WorkOrderBatchEnvelope,
)
def supplier_processing_qc_release(
    batch_id: int,
    user: dict = Depends(require_any_permission(QC_INSPECT, csrf=True)),
):
    ensure_department_access(user, "qc")
    return {
        "data": release_supplier_processing_batch(
            batch_id=batch_id,
            actor_username=user["username"],
            actor_department=user["department"],
            actor_is_system=user["is_system"],
        )
    }


@router.get("/inspection-batches", response_model=QcInspectionBatchListEnvelope)
def qc_inspection_batches(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    history: bool = Query(default=False),
    keyword: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_any_permission(QC_INSPECT)),
):
    ensure_department_access(user, "qc")
    data, total = qc_department.list_qc_inspection_batches(
        page,
        page_size,
        history,
        keyword,
    )
    return {"data": data, "total": total}


@router.get(
    "/work-orders/{work_order_id}",
    response_model=ProductionProgressWorkOrderResponse,
)
def qc_work_order_detail(
    work_order_id: int,
    user: dict = Depends(require_any_permission(QC_INSPECT)),
):
    ensure_department_access(user, "qc")
    return qc_department.get_qc_work_order_detail(work_order_id)


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
    "/work-order-batches/{batch_id}/inspection/undo",
    status_code=status.HTTP_204_NO_CONTENT,
)
def qc_batch_inspection_undo(
    batch_id: int,
    user: dict = Depends(require_any_permission(QC_INSPECT, csrf=True)),
):
    ensure_department_access(user, "qc")
    qc_department.undo_qc_inspection(
        batch_id,
        user["department"],
        user["is_system"],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.post(
    "/work-order-batches/{batch_id}/destination/undo",
    response_model=WorkOrderEnvelope,
)
def qc_batch_destination_undo(
    batch_id: int,
    user: dict = Depends(require_any_permission(QC_INSPECT, csrf=True)),
):
    ensure_department_access(user, "qc")
    return {
        "data": qc_department.undo_qc_destination(
            batch_id,
            user["username"],
            user["department"],
            user["is_system"],
        )
    }
