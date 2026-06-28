from fastapi import APIRouter, Depends, HTTPException

from models.production import Procedure, Task, Worker
from schemas.production import CreateProcedurePayload, CreateTaskPayload
from security import ensure_department_access, require_any_permission

router = APIRouter(prefix="/tasks", tags=["tasks"])


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


@router.post("")
def create_task(
    payload: CreateTaskPayload,
    user: dict = Depends(require_any_permission("task:assign", csrf=True)),
):
    order_id = payload.order_id.strip()
    zz_code = payload.zz_code.strip()
    product = payload.product.strip()
    worker = payload.worker.strip()
    department = payload.department.strip()
    procedure = payload.procedure.strip()

    if not all((order_id, zz_code, product, worker, department, procedure)):
        raise HTTPException(status_code=400, detail="任务必填信息不能为空")

    ensure_department_access(user, department)
    try:
        task = Task.create(
            order_id=order_id,
            zz_code=zz_code,
            product=product,
            worker=worker,
            department=department,
            procedure=procedure,
            quantity=payload.quantity,
            note=normalize_optional_text(payload.note),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"data": task}


@router.patch("/{task_id}/complete")
def complete_task(
    task_id: int,
    user: dict = Depends(require_any_permission("task:complete", csrf=True)),
):
    try:
        task = Task.complete(task_id, allowed_department=user["department"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"data": task}


@router.get("/{department}/workers")
def list_department_workers(
    department: str,
    user: dict = Depends(require_any_permission("task:view")),
):
    ensure_department_access(user, department.strip())
    return {"data": Worker.list_by_department(department.strip())}


@router.get("/{department}/procedures")
def list_department_procedures(
    department: str,
    user: dict = Depends(require_any_permission("task:view")),
):
    ensure_department_access(user, department.strip())
    return {"data": Procedure.list_by_department(department.strip())}


@router.post("/{department}/procedures")
def create_department_procedure(
    department: str,
    payload: CreateProcedurePayload,
    user: dict = Depends(require_any_permission("task:assign", csrf=True)),
):
    procedure_name = payload.procedure_name.strip()
    resolved_department = department.strip()
    ensure_department_access(user, resolved_department)

    if not procedure_name:
        raise HTTPException(status_code=400, detail="工艺名称不能为空")

    if payload.department.strip() != resolved_department:
        raise HTTPException(status_code=400, detail="部门不一致")

    try:
        procedure = Procedure.create(
            department=resolved_department,
            procedure_name=procedure_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"data": procedure}


@router.get("/{department}")
def list_department_tasks(
    department: str,
    user: dict = Depends(require_any_permission("task:view")),
):
    ensure_department_access(user, department.strip())
    return {"data": Task.list_by_department(department.strip())}
