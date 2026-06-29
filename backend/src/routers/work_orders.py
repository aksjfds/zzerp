from fastapi import APIRouter, Depends, HTTPException

from models.production import DepartmentProcess, Procedure, WorkOrder, Worker
from schemas.production import (
    ConfigureProcessesPayload,
    CreateProcedurePayload,
    CreateSubmissionPayload,
    CreateWorkerPayload,
    CreateWorkOrderPayload,
    DirectReportPayload,
)
from security import ensure_department_access, require_any_permission


router = APIRouter(prefix="/work-orders", tags=["work-orders"])


def _normalize_required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name}不能为空")
    return normalized


@router.get("/{department}/workers")
def list_workers(
    department: str,
    user: dict = Depends(require_any_permission("task:view")),
):
    resolved_department = department.strip()
    ensure_department_access(user, resolved_department)
    return {"data": Worker.list_by_department(resolved_department)}


@router.post("/{department}/workers")
def create_worker(
    department: str,
    payload: CreateWorkerPayload,
    user: dict = Depends(require_any_permission("task:assign", csrf=True)),
):
    resolved_department = department.strip()
    ensure_department_access(user, resolved_department)
    return {
        "data": Worker.create(
            department=resolved_department,
            name=_normalize_required(payload.name, "工人姓名"),
        )
    }


@router.get("/{department}/procedures")
def list_procedures(
    department: str,
    user: dict = Depends(require_any_permission("task:view")),
):
    resolved_department = department.strip()
    ensure_department_access(user, resolved_department)
    return {"data": Procedure.list_by_department(resolved_department)}


@router.post("/{department}/procedures")
def create_procedure(
    department: str,
    payload: CreateProcedurePayload,
    user: dict = Depends(require_any_permission("task:assign", csrf=True)),
):
    resolved_department = department.strip()
    ensure_department_access(user, resolved_department)
    if payload.department.strip() != resolved_department:
        raise HTTPException(status_code=400, detail="部门不一致")
    return {
        "data": Procedure.create(
            department=resolved_department,
            procedure_name=_normalize_required(payload.procedure_name, "工艺名称"),
        )
    }


@router.get("/{department}/processes")
def list_processes(
    department: str,
    user: dict = Depends(require_any_permission("task:view")),
):
    resolved_department = department.strip()
    ensure_department_access(user, resolved_department)
    return {"data": DepartmentProcess.list_by_department(resolved_department)}


@router.post("/{department}/processes")
def configure_processes(
    department: str,
    payload: ConfigureProcessesPayload,
    user: dict = Depends(require_any_permission("task:assign", csrf=True)),
):
    resolved_department = department.strip()
    ensure_department_access(user, resolved_department)
    try:
        data = DepartmentProcess.configure(
            product_id=payload.product_id,
            department=resolved_department,
            steps=[step.model_dump() for step in payload.steps],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.post("")
def create_work_order(
    payload: CreateWorkOrderPayload,
    user: dict = Depends(require_any_permission("task:assign", csrf=True)),
):
    try:
        data = WorkOrder.create(
            product_id=payload.product_id,
            process_id=payload.process_id,
            worker_id=payload.worker_id,
            issued_quantity=payload.quantity,
            created_by=user["id"],
            allowed_department=user["department"],
            note=payload.note.strip() if payload.note and payload.note.strip() else None,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.post("/{work_order_id}/submissions")
def create_submission(
    work_order_id: int,
    payload: CreateSubmissionPayload,
    user: dict = Depends(require_any_permission("task:complete", csrf=True)),
):
    try:
        data = WorkOrder.create_submission(
            work_order_id=work_order_id,
            quantity=payload.quantity,
            submitted_by=user["id"],
            allowed_department=user["department"],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.post("/{work_order_id}/direct-reports")
def create_direct_report(
    work_order_id: int,
    payload: DirectReportPayload,
    user: dict = Depends(require_any_permission("task:complete", csrf=True)),
):
    try:
        data = WorkOrder.create_direct_report(
            work_order_id=work_order_id,
            ok_quantity=payload.ok_quantity,
            scrap_quantity=payload.scrap_quantity,
            lost_quantity=payload.lost_quantity,
            reason=payload.reason.strip() if payload.reason and payload.reason.strip() else None,
            submitted_by=user["id"],
            allowed_department=user["department"],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": data}


@router.get("/{department}")
def list_work_orders(
    department: str,
    user: dict = Depends(require_any_permission("task:view")),
):
    resolved_department = department.strip()
    ensure_department_access(user, resolved_department)
    return {"data": WorkOrder.list_by_department(resolved_department)}
