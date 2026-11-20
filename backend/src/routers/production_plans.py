from typing import Annotated, Literal

from authorization import require_any_permission
from domain.permissions import (
    DEPARTMENT_WORK_ORDER_OPERATE,
    DEPARTMENT_WORK_ORDER_VIEW,
    PLAN_ADD,
    PLAN_CANCEL,
    PLAN_CONFIRM,
    PLAN_EDIT,
    PLAN_VIEW,
)
from fastapi import APIRouter, Depends, Query, Response, status
from modules.planning.api import (
    change_plan_status,
    create_plan,
    create_purchase,
    delete_plan,
    department_warehouse_stocks,
    dispatch_outsource,
    dispatch_plans,
    dispatch_targets,
    dispatch_warehouse,
    get_handoff_options,
    get_plan,
    get_plan_product_snapshot,
    get_schedule_context,
    inspect_material,
    list_department_movements,
    list_handoff_tickets,
    list_movements,
    list_plans,
    list_production_progress,
    list_work_orders,
    outsource_receipts,
    purchase_work_orders,
    qc_history,
    qc_repair_targets,
    qc_source_origin,
    receive_purchase,
    record_movement,
    record_rework,
    return_outsource,
    revoke_operation,
    update_plan,
    update_work_order_schedule,
    warehouse_picks,
    warehouse_stocks,
    worker_piecework,
)
from schemas.outsourcing import (
    OutsourceCommandEnvelope,
    OutsourceDispatchCreate,
    OutsourceReceiptEnvelope,
    OutsourceReturnCreate,
)
from schemas.planning import (
    DepartmentMovementCreate,
    DepartmentMovementEnvelope,
    DepartmentMovementListEnvelope,
    DepartmentWorkOrderListEnvelope,
    HandoffOptionsResponse,
    HandoffTicketListEnvelope,
    PlanProductSnapshotEnvelope,
    ProductionPlanCreate,
    ProductionPlanEnvelope,
    ProductionPlanListEnvelope,
    ProductionPlanUpdate,
    ProductionProgressEnvelope,
    WorkOrderScheduleEnvelope,
    WorkOrderScheduleUpdate,
)
from schemas.purchasing import (
    PurchaseCommandEnvelope,
    PurchaseCreate,
    PurchaseWorkOrderEnvelope,
)
from schemas.quality import (
    QcCommandEnvelope,
    QcInspectionCreate,
    QcListEnvelope,
    QcOriginEnvelope,
    QcReworkAction,
    QcTargetsEnvelope,
    WorkerEnvelope,
)
from schemas.revocations import DepartmentLedgerEnvelope, OperationKind, RevokeOperation
from schemas.warehouse import (
    WarehouseDispatchCreate,
    WarehouseDispatchEnvelope,
    WarehouseDispatchPlansEnvelope,
    WarehouseDispatchTargetsEnvelope,
    WarehousePicksEnvelope,
    WarehouseStocksEnvelope,
)

PlanReader = Annotated[dict, Depends(require_any_permission(PLAN_VIEW))]
PlanCreator = Annotated[dict, Depends(require_any_permission(PLAN_ADD, csrf=True))]
PlanEditor = Annotated[dict, Depends(require_any_permission(PLAN_EDIT, csrf=True))]
PlanCanceller = Annotated[dict, Depends(require_any_permission(PLAN_CANCEL, csrf=True))]
PlanConfirmer = Annotated[dict, Depends(require_any_permission(PLAN_CONFIRM, csrf=True))]
WorkOrderReader = Annotated[dict, Depends(require_any_permission(PLAN_VIEW, DEPARTMENT_WORK_ORDER_VIEW))]
MovementOperator = Annotated[dict, Depends(require_any_permission(DEPARTMENT_WORK_ORDER_OPERATE, csrf=True))]

router = APIRouter(prefix="/production-plans", tags=["production-plans"])


@router.get('/purchasing/work-orders', response_model=PurchaseWorkOrderEnvelope)
def purchasing_orders(page: int = Query(default=1, gt=0), page_size: int = Query(default=50, gt=0, le=100), *, user: WorkOrderReader):
    data, total = purchase_work_orders(page, page_size, department_scope=user['department_code'])
    return {'data': data, 'total': total}


@router.post('/purchasing/work-orders/{work_order_id}', response_model=PurchaseCommandEnvelope)
def purchasing_create(work_order_id: int, payload: PurchaseCreate, *, user: MovementOperator):
    return create_purchase(work_order_id, payload, department_scope=user['department_code'], actor_user_id=user['id'])


@router.post('/purchasing/{purchase_id}/receipts', response_model=PurchaseCommandEnvelope)
def purchasing_receive(purchase_id: int, payload: PurchaseCreate, *, user: MovementOperator):
    return receive_purchase(purchase_id, payload, department_scope=user['department_code'], actor_user_id=user['id'])


@router.post('/operations/{kind}/{operation_id}/revoke', response_model=OutsourceCommandEnvelope)
def operation_revoke(kind: OperationKind, operation_id: int, payload: RevokeOperation, *, user: MovementOperator):
    return revoke_operation(kind, operation_id, payload, department_scope=user['department_code'], actor_user_id=user['id'])


@router.get('/outsourcing/receipts', response_model=OutsourceReceiptEnvelope)
def outsourcing_receipts(page: int = Query(default=1, gt=0), page_size: int = Query(default=50, gt=0, le=100), receipt_id: int | None = Query(default=None, gt=0), *, user: WorkOrderReader):
    data, total = outsource_receipts(page, page_size, department_scope=user['department_code'], receipt_id=receipt_id)
    return {'data': data, 'total': total}


@router.post('/outsourcing/dispatches', response_model=OutsourceCommandEnvelope)
def outsourcing_dispatch(payload: OutsourceDispatchCreate, *, user: MovementOperator):
    return dispatch_outsource(payload, department_scope=user['department_code'], actor_user_id=user['id'])


@router.post('/outsourcing/dispatches/{dispatch_id}/returns', response_model=OutsourceCommandEnvelope)
def outsourcing_return(dispatch_id: int, payload: OutsourceReturnCreate, *, user: MovementOperator):
    return return_outsource(dispatch_id, payload, department_scope=user['department_code'], actor_user_id=user['id'])


@router.get("", response_model=ProductionPlanListEnvelope)
def plan_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    *, _: PlanReader,
):
    data, total = list_plans(page, page_size)
    return {"data": data, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProductionPlanEnvelope)
def plan_create(
    payload: ProductionPlanCreate,
    *, _: PlanCreator,
):
    return {"data": create_plan(payload)}


@router.get("/department-work-orders", response_model=DepartmentWorkOrderListEnvelope)
def department_work_order_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    department_code: str | None = Query(default=None, max_length=50),
    plan_id: int | None = Query(default=None, gt=0),
    work_order_id: int | None = Query(default=None, gt=0),
    order_no: str | None = Query(default=None, max_length=200),
    product_keyword: str | None = Query(default=None, max_length=200),
    *, user: WorkOrderReader,
):
    data, total = list_work_orders(page, page_size, department_scope=user["department_code"], department_code=department_code,
                                  plan_id=plan_id, work_order_id=work_order_id, order_no=order_no, product_keyword=product_keyword)
    return {"data": data, "total": total}


@router.put("/department-work-orders/{order_id}/schedule", response_model=WorkOrderScheduleEnvelope)
def work_order_schedule(order_id: int, payload: WorkOrderScheduleUpdate, *, user: PlanEditor):
    return {"data": update_work_order_schedule(order_id, payload, department_scope=user["department_code"])}


@router.get("/department-work-orders/{order_id}/schedule-context", response_model=WorkOrderScheduleEnvelope)
def work_order_schedule_context(order_id: int, *, user: PlanEditor):
    return {"data": get_schedule_context(order_id, department_scope=user["department_code"])}


@router.get("/progress", response_model=ProductionProgressEnvelope)
def production_progress(
    page: int = Query(default=1, gt=0), page_size: int = Query(default=20, gt=0, le=50),
    order_no: str | None = Query(default=None, max_length=200),
    product_keyword: str | None = Query(default=None, max_length=200),
    *, user: PlanReader,
):
    data, total = list_production_progress(page, page_size, department_scope=user["department_code"],
                                          order_no=order_no, product_keyword=product_keyword)
    return {"data": data, "total": total}


@router.get("/department-movements", response_model=DepartmentLedgerEnvelope)
def department_ledger(
    page: int = Query(default=1, gt=0), page_size: int = Query(default=50, gt=0, le=200),
    department_code: str | None = Query(default=None, max_length=50),
    *, user: WorkOrderReader,
):
    data,total = list_department_movements(page,page_size,department_scope=user["department_code"],department_code=department_code)
    return {"data":data,"total":total}


@router.get("/handoff-tickets", response_model=HandoffTicketListEnvelope)
def handoff_ticket_list(
    direction: Literal['incoming', 'outgoing'] = 'incoming',
    page: int = Query(default=1, gt=0), page_size: int = Query(default=50, gt=0, le=200),
    unreceived: bool = False, order_no: str | None = Query(default=None, max_length=200),
    target_order_id: int | None = Query(default=None, gt=0),
    department_code: str | None = Query(default=None, max_length=50),
    *, user: WorkOrderReader,
):
    data,total = list_handoff_tickets(page,page_size,department_scope=user["department_code"],
        unreceived=unreceived,order_no=order_no,target_order_id=target_order_id,department_code=department_code,direction=direction)
    return {"data": data,"total": total}


@router.get("/department-work-orders/{order_id}/handoff-options", response_model=HandoffOptionsResponse)
def handoff_options(order_id: int, *, user: WorkOrderReader):
    return get_handoff_options(order_id, department_scope=user["department_code"])


@router.get("/department-work-orders/{order_id}/movements", response_model=DepartmentMovementListEnvelope)
def department_movement_list(
    order_id: int,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    input_material_node_id: str | None = Query(default=None, min_length=1, max_length=100),
    *, user: WorkOrderReader,
):
    data, total = list_movements(order_id, page, page_size, department_scope=user["department_code"],
                                 input_material_node_id=input_material_node_id)
    return {"data": data, "total": total}


@router.post("/department-work-orders/{order_id}/movements", response_model=DepartmentMovementEnvelope)
def department_movement_create(
    order_id: int,
    payload: DepartmentMovementCreate,
    *, user: MovementOperator,
):
    return {"data": record_movement(order_id, payload, department_scope=user["department_code"], actor_user_id=user["id"])}


@router.get("/warehouse/stocks", response_model=WarehouseStocksEnvelope)
def warehouse_stock_list(page: int = Query(default=1, gt=0), page_size: int = Query(default=50, gt=0, le=100), *, user: WorkOrderReader):
    data, total = warehouse_stocks(page, page_size, department_scope=user["department_code"])
    return {"data": data, "total": total}


@router.get("/warehouse/picks", response_model=WarehousePicksEnvelope)
def warehouse_pick_list(page: int = Query(default=1, gt=0), page_size: int = Query(default=50, gt=0, le=100), pick_id: int | None = Query(default=None, gt=0), *, user: WorkOrderReader):
    data, total = warehouse_picks(page, page_size, department_scope=user["department_code"], pick_id=pick_id)
    return {"data": data, "total": total}


@router.get("/warehouse/department-stocks", response_model=WarehouseStocksEnvelope)
def department_stock_list(page: int = Query(default=1, gt=0), page_size: int = Query(default=50, gt=0, le=100), department_code: str | None = None, *, user: WorkOrderReader):
    data, total = department_warehouse_stocks(page, page_size, department_scope=user["department_code"], department_code=department_code)
    return {"data": data, "total": total}


@router.post("/warehouse/orders/{order_id}/dispatch", response_model=WarehouseDispatchEnvelope)
def warehouse_dispatch(order_id: int, payload: WarehouseDispatchCreate, *, user: MovementOperator):
    return dispatch_warehouse(order_id, payload, department_scope=user["department_code"], actor_user_id=user["id"])


@router.get("/warehouse/lots/{lot_id}/dispatch-plans", response_model=WarehouseDispatchPlansEnvelope)
def warehouse_dispatch_plans(lot_id: int, keyword: str | None = Query(default=None, max_length=200), *, user: WorkOrderReader):
    return {"data": dispatch_plans(lot_id, keyword, department_scope=user["department_code"])}


@router.get("/warehouse/lots/{lot_id}/dispatch-targets", response_model=WarehouseDispatchTargetsEnvelope)
def warehouse_dispatch_targets(lot_id: int, plan_id: int = Query(gt=0), *, user: WorkOrderReader):
    return {"data": dispatch_targets(lot_id, plan_id, department_scope=user["department_code"])}


@router.get("/qc/history", response_model=QcListEnvelope)
def quality_history(page: int = Query(default=1, gt=0), page_size: int = Query(default=50, gt=0, le=100), *, user: WorkOrderReader):
    data, total = qc_history(page, page_size, department_scope=user["department_code"])
    return {"data": data, "total": total}


@router.get('/piecework/workers', response_model=WorkerEnvelope)
def piecework_workers(page: int = Query(default=1, gt=0), page_size: int = Query(default=20, gt=0, le=50), worker_name: str | None = Query(default=None, max_length=100), *, user: WorkOrderReader):
    data, total = worker_piecework(page, page_size, worker_name, department_scope=user['department_code'])
    return {'data': data, 'total': total}


@router.get('/qc/source-origin', response_model=QcOriginEnvelope)
def quality_source_origin(source_kind: Literal['handoff', 'return', 'warehouse'], source_id: int = Query(gt=0), *, user: WorkOrderReader):
    return {'data': qc_source_origin(source_kind, source_id, department_scope=user['department_code'])}


@router.get("/qc/orders/{order_id}/targets", response_model=QcTargetsEnvelope)
def quality_targets(order_id: int, *, user: WorkOrderReader):
    return {"data": qc_repair_targets(order_id, department_scope=user["department_code"])}


@router.post("/qc/inspections", response_model=QcCommandEnvelope)
def quality_inspection(payload: QcInspectionCreate, *, user: MovementOperator):
    return {"data": inspect_material(payload, department_scope=user["department_code"], actor_user_id=user["id"])}


@router.post("/qc/rework/{ticket_id}/events", response_model=QcCommandEnvelope)
def quality_rework_event(ticket_id: int, payload: QcReworkAction, *, user: MovementOperator):
    return {"data": record_rework(ticket_id, payload, department_scope=user["department_code"], actor_user_id=user["id"])}


@router.get("/{plan_id}/products/{product_id}/snapshot", response_model=PlanProductSnapshotEnvelope)
def plan_product_snapshot(plan_id: int, product_id: int, *, user: PlanReader):
    return {"data": get_plan_product_snapshot(plan_id, product_id, department_scope=user["department_code"])}


@router.get("/{plan_id}", response_model=ProductionPlanEnvelope)
def plan_detail(plan_id: int, *, _: PlanReader):
    return {"data": get_plan(plan_id)}


@router.put("/{plan_id}", response_model=ProductionPlanEnvelope)
def plan_update(
    plan_id: int,
    payload: ProductionPlanUpdate,
    *, _: PlanEditor,
):
    return {"data": update_plan(plan_id, payload)}


@router.post("/{plan_id}/cancel", response_model=ProductionPlanEnvelope)
def plan_cancel(
    plan_id: int,
    expected_revision: int = Query(gt=0),
    *, user: PlanCanceller,
):
    return {"data": change_plan_status(plan_id, "cancel", expected_revision, user["username"])}


@router.post("/{plan_id}/{action}", response_model=ProductionPlanEnvelope)
def plan_status(
    plan_id: int,
    action: Literal["confirm", "unconfirm", "complete", "reopen"],
    expected_revision: int = Query(gt=0),
    *, user: PlanConfirmer,
):
    return {"data": change_plan_status(plan_id, action, expected_revision, user["username"])}


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def plan_delete(
    plan_id: int,
    expected_revision: int = Query(gt=0),
    *, _: PlanEditor,
):
    delete_plan(plan_id, expected_revision)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
