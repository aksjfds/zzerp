from fastapi import APIRouter, Depends

from authorization import ensure_department_access, require_any_permission
from departments.work_order_commands import create_department_source_work_order
from domain.permissions import PRODUCTION_MANAGE
from schemas.production import (
    AssemblyWorkOrderCreate,
    ReworkSubmission,
    WorkOrderCreate,
    WorkOrderBatchEnvelope,
    WorkOrderEnvelope,
    WorkOrderSubmission,
)
from departments.contracts import CAP_ASSEMBLY
from departments.registry import department_api
from departments.work_order_orchestration import (
    cancel_work_order,
    resubmit_work_order_rework_batch,
    submit_work_order,
    undo_work_order_operation,
)


router = APIRouter(tags=["work-orders"])


@router.post("/work-orders", response_model=WorkOrderEnvelope)
def work_order_create(
    payload: WorkOrderCreate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": create_department_source_work_order(
            actor_department=user["department"],
            actor_is_system=user["is_system"],
            repository_id=payload.repository_id,
            procedure_id=payload.procedure_id,
            procedure_name=payload.procedure_name,
            is_temporary=payload.is_temporary,
            quantity=payload.quantity,
            worker_id=payload.worker_id,
            remark=payload.remark,
            actor_username=user["username"],
        )
    }


@router.post("/assembly-work-orders", response_model=WorkOrderEnvelope)
def assembly_work_order_create(
    payload: AssemblyWorkOrderCreate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    ensure_department_access(user, "assembly")
    return {
        "data": department_api(
            "assembly",
            CAP_ASSEMBLY,
        ).create_assembly_work_order(
            [item.model_dump() for item in payload.materials],
            payload.procedure_id,
            payload.procedure_name,
            payload.is_temporary,
            payload.quantity,
            payload.worker_id,
            payload.remark,
            user["username"],
            user["department"],
            user["is_system"],
        )
    }


@router.post("/work-orders/{work_order_id}/submissions", response_model=WorkOrderEnvelope)
def work_order_submit(
    work_order_id: int,
    payload: WorkOrderSubmission,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": submit_work_order(
            work_order_id,
            payload.completion_action,
            user["department"],
            user["is_system"],
            user["username"],
        )
    }


@router.post(
    "/work-order-batches/{batch_id}/rework-submissions",
    response_model=WorkOrderBatchEnvelope,
)
def work_order_batch_rework_submit(
    batch_id: int,
    payload: ReworkSubmission,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": resubmit_work_order_rework_batch(
            batch_id,
            payload.quantity,
            user["department"],
            user["is_system"],
            user["username"],
        )
    }


@router.post(
    "/production-operations/{operation_id}/undo",
    response_model=WorkOrderEnvelope,
)
def production_operation_undo(
    operation_id: int,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": undo_work_order_operation(
            operation_id,
            user["department"],
            user["is_system"],
            user["username"],
        )
    }


@router.post("/work-orders/{work_order_id}/cancel", response_model=WorkOrderEnvelope)
def work_order_cancel(
    work_order_id: int,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": cancel_work_order(
            work_order_id,
            user["department"],
            user["is_system"],
        )
    }
