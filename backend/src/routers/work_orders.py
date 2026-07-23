from fastapi import APIRouter, Depends, HTTPException, Query

from authorization import require_any_permission
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW
from schemas.production import (
    AssemblyWorkOrderCreate,
    ReworkSubmission,
    WorkOrderCreate,
    WorkOrderBatchEnvelope,
    WorkOrderEnvelope,
    WorkOrderListEnvelope,
    WorkOrderSubmission,
)
from services.assembly_work_orders import create_assembly_work_order
from services.process_work_orders import (
    cancel_work_order,
    create_work_order,
    resubmit_work_order_rework_batch,
    submit_work_order,
)
from services.work_order_queries import list_department_work_orders
from services.production_operation_undo import undo_production_operation


router = APIRouter(tags=["work-orders"])


@router.get(
    "/departments/{department_code}/work-orders",
    response_model=WorkOrderListEnvelope,
)
def department_work_orders(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    production_item_id: int | None = Query(default=None, gt=0),
    flow_node_id: str | None = Query(default=None, min_length=1, max_length=200),
    source_flow_node_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    existing_tag_id: list[int] | None = Query(default=None),
    applying_tag_id: list[int] | None = Query(default=None),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    data, total = list_department_work_orders(
        department_code=department_code,
        page=page,
        page_size=page_size,
        production_item_id=production_item_id,
        flow_node_id=flow_node_id,
        source_flow_node_id=source_flow_node_id,
        existing_tag_ids=existing_tag_id,
        applying_tag_ids=applying_tag_id,
    )
    return {"data": data, "total": total}


@router.post("/work-orders", response_model=WorkOrderEnvelope)
def work_order_create(
    payload: WorkOrderCreate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": create_work_order(
            payload.repository_id,
            payload.procedure_tag_stock_id,
            payload.tag_names,
            payload.quantity,
            payload.worker_id,
            payload.remark,
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
            payload.remark,
            user["department"],
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
            payload.quantity,
            payload.completion_action,
            user["department"],
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
        "data": undo_production_operation(
            operation_id,
            user["department"],
            user["username"],
        )
    }


@router.post("/work-orders/{work_order_id}/cancel", response_model=WorkOrderEnvelope)
def work_order_cancel(
    work_order_id: int,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {"data": cancel_work_order(work_order_id, user["department"])}
