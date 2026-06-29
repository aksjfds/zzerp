from fastapi import APIRouter, Depends, HTTPException

from models.production import WorkOrder
from schemas.production import AssignQcWorkerPayload, InspectionPayload
from security import require_any_permission


router = APIRouter(prefix="/qc", tags=["qc"])


@router.get("/submissions/pending")
def list_pending_submissions(
    user: dict = Depends(require_any_permission("task:view")),
):
    if user["department"] not in {"sys", "qc"}:
        raise HTTPException(status_code=403, detail="只有 QC 可以查看待质检批次")
    return {"data": WorkOrder.pending_qc()}


@router.post("/submissions/{batch_id}/assignment")
def assign_submission(
    batch_id: int,
    payload: AssignQcWorkerPayload,
    user: dict = Depends(require_any_permission("task:assign", csrf=True)),
):
    try:
        data = WorkOrder.assign_qc_worker(
            batch_id=batch_id,
            qc_worker_id=payload.qc_worker_id,
            allowed_department=user["department"],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.post("/submissions/{batch_id}/inspection")
def inspect_submission(
    batch_id: int,
    payload: InspectionPayload,
    user: dict = Depends(require_any_permission("task:complete", csrf=True)),
):
    try:
        data = WorkOrder.inspect_submission(
            batch_id=batch_id,
            ok_quantity=payload.ok_quantity,
            rework_quantity=payload.rework_quantity,
            scrap_quantity=payload.scrap_quantity,
            lost_quantity=payload.lost_quantity,
            defect_reason=(
                payload.defect_reason.strip()
                if payload.defect_reason and payload.defect_reason.strip()
                else None
            ),
            inspected_by=user["id"],
            allowed_department=user["department"],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}
