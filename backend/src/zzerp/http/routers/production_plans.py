from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from zzerp.database import Database
from zzerp.http.authorization import require_any_permission
from zzerp.http.dependencies import get_database
from zzerp.modules.identity.contracts import (
    DEPARTMENT_WORK_ORDER_OPERATE,
    DEPARTMENT_WORK_ORDER_VIEW,
    PLAN_ADD,
    PLAN_CANCEL,
    PLAN_CONFIRM,
    PLAN_EDIT,
    PLAN_VIEW,
    UserResponse,
)
from zzerp.modules.planning.api import (
    change_plan_status,
    create_plan,
    delete_plan,
    get_handoff_options,
    get_plan,
    list_department_movements,
    list_handoff_tickets,
    list_movements,
    list_plans,
    list_production_progress,
    list_work_orders,
    record_movement,
    update_plan,
)
from zzerp.modules.planning.contracts import (
    DepartmentLedgerEnvelope,
    DepartmentMovementCreate,
    DepartmentMovementEnvelope,
    DepartmentMovementListEnvelope,
    DepartmentWorkOrderListEnvelope,
    HandoffOptionsResponse,
    HandoffTicketListEnvelope,
    ProductionPlanCreate,
    ProductionPlanEnvelope,
    ProductionPlanListEnvelope,
    ProductionPlanUpdate,
    ProductionProgressEnvelope,
)

router = APIRouter(prefix="/production-plans", tags=["production-plans"])


@router.get("", response_model=ProductionPlanListEnvelope)
def plan_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    _: UserResponse = Depends(require_any_permission(PLAN_VIEW)),
    database: Database = Depends(get_database),
):
    data, total = database.query(list_plans, page, page_size)
    return {"data": data, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProductionPlanEnvelope)
def plan_create(
    payload: ProductionPlanCreate,
    _: UserResponse = Depends(require_any_permission(PLAN_ADD, csrf=True)),
    database: Database = Depends(get_database),
):
    return {"data": database.command(create_plan, payload)}


@router.get("/department-work-orders", response_model=DepartmentWorkOrderListEnvelope)
def department_work_order_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    department_code: str | None = Query(default=None, max_length=50),
    plan_id: int | None = Query(default=None, gt=0),
    work_order_id: int | None = Query(default=None, gt=0),
    order_no: str | None = Query(default=None, max_length=200),
    product_keyword: str | None = Query(default=None, max_length=200),
    user: UserResponse = Depends(require_any_permission(PLAN_VIEW, DEPARTMENT_WORK_ORDER_VIEW)),
    database: Database = Depends(get_database),
):
    data, total = database.query(
        list_work_orders,
        page,
        page_size,
        department_scope=user.department_code,
        department_code=department_code,
        plan_id=plan_id,
        work_order_id=work_order_id,
        order_no=order_no,
        product_keyword=product_keyword,
    )
    return {"data": data, "total": total}


@router.get("/progress", response_model=ProductionProgressEnvelope)
def production_progress(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=20, gt=0, le=50),
    order_no: str | None = Query(default=None, max_length=200),
    product_keyword: str | None = Query(default=None, max_length=200),
    user: UserResponse = Depends(require_any_permission(PLAN_VIEW)),
    database: Database = Depends(get_database),
):
    data, total = database.query(
        list_production_progress,
        page,
        page_size,
        department_scope=user.department_code,
        order_no=order_no,
        product_keyword=product_keyword,
    )
    return {"data": data, "total": total}


@router.get("/department-movements", response_model=DepartmentLedgerEnvelope)
def department_ledger(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    department_code: str | None = Query(default=None, max_length=50),
    user: UserResponse = Depends(require_any_permission(PLAN_VIEW, DEPARTMENT_WORK_ORDER_VIEW)),
    database: Database = Depends(get_database),
):
    data, total = database.query(
        list_department_movements,
        page,
        page_size,
        department_scope=user.department_code,
        department_code=department_code,
    )
    return {"data": data, "total": total}


@router.get("/handoff-tickets", response_model=HandoffTicketListEnvelope)
def handoff_ticket_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    unreceived: bool = False,
    order_no: str | None = Query(default=None, max_length=200),
    target_order_id: int | None = Query(default=None, gt=0),
    department_code: str | None = Query(default=None, max_length=50),
    user: UserResponse = Depends(require_any_permission(PLAN_VIEW, DEPARTMENT_WORK_ORDER_VIEW)),
    database: Database = Depends(get_database),
):
    data, total = database.query(
        list_handoff_tickets,
        page,
        page_size,
        department_scope=user.department_code,
        unreceived=unreceived,
        order_no=order_no,
        target_order_id=target_order_id,
        department_code=department_code,
    )
    return {"data": data, "total": total}


@router.get(
    "/department-work-orders/{order_id}/handoff-options", response_model=HandoffOptionsResponse
)
def handoff_options(
    order_id: int,
    user: UserResponse = Depends(require_any_permission(PLAN_VIEW, DEPARTMENT_WORK_ORDER_VIEW)),
    database: Database = Depends(get_database),
):
    return database.query(get_handoff_options, order_id, department_scope=user.department_code)


@router.get(
    "/department-work-orders/{order_id}/movements", response_model=DepartmentMovementListEnvelope
)
def department_movement_list(
    order_id: int,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    input_material_node_id: str | None = Query(default=None, min_length=1, max_length=100),
    user: UserResponse = Depends(require_any_permission(PLAN_VIEW, DEPARTMENT_WORK_ORDER_VIEW)),
    database: Database = Depends(get_database),
):
    data, total = database.query(
        list_movements,
        order_id,
        page,
        page_size,
        department_scope=user.department_code,
        input_material_node_id=input_material_node_id,
    )
    return {"data": data, "total": total}


@router.post(
    "/department-work-orders/{order_id}/movements", response_model=DepartmentMovementEnvelope
)
def department_movement_create(
    order_id: int,
    payload: DepartmentMovementCreate,
    user: UserResponse = Depends(require_any_permission(DEPARTMENT_WORK_ORDER_OPERATE, csrf=True)),
    database: Database = Depends(get_database),
):
    return {
        "data": database.command(
            record_movement,
            order_id,
            payload,
            department_scope=user.department_code,
            actor_user_id=user.id,
        )
    }


@router.get("/{plan_id}", response_model=ProductionPlanEnvelope)
def plan_detail(
    plan_id: int,
    _: UserResponse = Depends(require_any_permission(PLAN_VIEW)),
    database: Database = Depends(get_database),
):
    return {"data": database.query(get_plan, plan_id)}


@router.put("/{plan_id}", response_model=ProductionPlanEnvelope)
def plan_update(
    plan_id: int,
    payload: ProductionPlanUpdate,
    _: UserResponse = Depends(require_any_permission(PLAN_EDIT, csrf=True)),
    database: Database = Depends(get_database),
):
    return {"data": database.command(update_plan, plan_id, payload)}


@router.post("/{plan_id}/cancel", response_model=ProductionPlanEnvelope)
def plan_cancel(
    plan_id: int,
    expected_revision: int = Query(gt=0),
    user: UserResponse = Depends(require_any_permission(PLAN_CANCEL, csrf=True)),
    database: Database = Depends(get_database),
):
    return {
        "data": database.command(
            change_plan_status, plan_id, "cancel", expected_revision, user.username
        )
    }


@router.post("/{plan_id}/{action}", response_model=ProductionPlanEnvelope)
def plan_status(
    plan_id: int,
    action: Literal["confirm", "unconfirm", "complete", "reopen"],
    expected_revision: int = Query(gt=0),
    user: UserResponse = Depends(require_any_permission(PLAN_CONFIRM, csrf=True)),
    database: Database = Depends(get_database),
):
    return {
        "data": database.command(
            change_plan_status, plan_id, action, expected_revision, user.username
        )
    }


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def plan_delete(
    plan_id: int,
    expected_revision: int = Query(gt=0),
    _: UserResponse = Depends(require_any_permission(PLAN_EDIT, csrf=True)),
    database: Database = Depends(get_database),
):
    database.command(delete_plan, plan_id, expected_revision)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
