from fastapi import APIRouter, HTTPException

from backend.src.models.production import Procedure, Task, Worker
from backend.src.types.production import CreateTaskPayload

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("")
def create_task(payload: CreateTaskPayload):
    try:
        task = Task.create(
            zz_code=payload.zz_code.strip(),
            product=payload.product.strip(),
            worker=payload.worker.strip(),
            department=payload.department.strip(),
            procedure=payload.procedure.strip(),
            quantity=payload.quantity,
            note=payload.note.strip() if payload.note else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"data": task}


@router.patch("/{task_id}/complete")
def complete_task(task_id: int):
    try:
        task = Task.complete(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"data": task}


@router.get("/{department}/workers")
def list_department_workers(department: str):
    return {"data": Worker.list_by_department(department.strip())}


@router.get("/{department}/procedures")
def list_department_procedures(department: str):
    return {"data": Procedure.list_by_department(department.strip())}


@router.get("/{department}")
def list_department_tasks(department: str):
    return {"data": Task.list_by_department(department.strip())}
