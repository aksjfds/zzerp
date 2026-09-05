from fastapi import APIRouter, Depends, Query, status

from authorization import ensure_department_access, require_any_permission
from domain.permissions import (
    SUPPLIER_PROCESSING_CREATE,
    SUPPLIER_PROCESSING_VIEW,
)
from modules.supplier_processing.api import (
    cancel_supplier_processing_work_order,
    create_supplier_processing_work_order,
    list_tasks,
)
from schemas.production_work_orders import WorkOrderEnvelope
from schemas.supplier_processing import (
    SupplierProcessingTaskListEnvelope,
    SupplierProcessingWorkOrderCreate,
)


router = APIRouter(prefix="/supplier-processing", tags=["supplier-processing"])


@router.get("/tasks", response_model=SupplierProcessingTaskListEnvelope)
def supplier_processing_tasks(
    production_plan_id: int | None = Query(default=None, gt=0),
    user: dict = Depends(require_any_permission(SUPPLIER_PROCESSING_VIEW)),
):
    ensure_department_access(user, "business")
    data, total = list_tasks(production_plan_id=production_plan_id)
    return {"data": data, "total": total}


@router.post(
    "/work-orders",
    status_code=status.HTTP_201_CREATED,
    response_model=WorkOrderEnvelope,
)
def supplier_processing_work_order_create(
    payload: SupplierProcessingWorkOrderCreate,
    user: dict = Depends(
        require_any_permission(SUPPLIER_PROCESSING_CREATE, csrf=True)
    ),
):
    ensure_department_access(user, "business")
    return {
        "data": create_supplier_processing_work_order(
            production_plan_item_id=payload.production_plan_item_id,
            supplier_flow_node_id=payload.supplier_flow_node_id,
            supplier_name=payload.supplier_name,
            supplier_process_name=payload.supplier_process_name,
            remark=payload.remark,
            actor_username=user["username"],
        )
    }


@router.post(
    "/work-orders/{work_order_id}/cancel",
    response_model=WorkOrderEnvelope,
)
def supplier_processing_work_order_cancel(
    work_order_id: int,
    user: dict = Depends(
        require_any_permission(SUPPLIER_PROCESSING_CREATE, csrf=True)
    ),
):
    ensure_department_access(user, "business")
    return {
        "data": cancel_supplier_processing_work_order(
            work_order_id=work_order_id,
            actor_username=user["username"],
        )
    }
