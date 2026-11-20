"""One-way withdrawal metadata, preserving all original business evidence."""

from database import SessionLocal
from domain.time import utc_now
from sqlalchemy import select

from modules.errors import DomainError
from modules.organization.read_api import operating_department
from modules.planning.current_records import OPERATION_MODELS, select_current
from modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrderMovement,
    OutsourceDispatch,
    OutsourceReturn,
    PurchaseOrder,
    PurchaseReceipt,
    QcInspection,
    QcReworkEvent,
    QcReworkTicket,
    WarehouseAllocation,
    WarehouseLot,
)
from modules.planning.queries import load_plan
from modules.planning.snapshots import route_key, route_references
from modules.planning.work_order_access import load_scoped_order


def operation_source(session, kind, row):
    if kind in {'movement', 'inspection'}:
        if kind == 'movement':
            order = load_scoped_order(session, row.work_order_id, None)
            if route_references(session, route_keys={route_key(order)})[route_key(order)].department_code == 'purchase':
                return row.work_order_id, 'warehouse'
        return row.work_order_id, None
    if kind == 'purchase':
        return row.work_order_id, 'warehouse'
    if kind == 'purchase_receipt':
        purchase = session.get(PurchaseOrder, row.purchase_order_id)
        return purchase.work_order_id, 'warehouse'
    if kind == 'warehouse':
        return row.target_order_id, 'warehouse'
    if kind == 'rework':
        ticket = session.get(QcReworkTicket, row.ticket_id)
        inspection = session.get(QcInspection, ticket.inspection_id)
        return inspection.work_order_id, operating_department(inspection.repair_department_code)
    dispatch = session.get(OutsourceDispatch, row.dispatch_id) if kind == 'outsource_return' else row
    receipt = session.get(DepartmentWorkOrderMovement, dispatch.receipt_id)
    return receipt.work_order_id, 'outsource'


def exists(session, model, *conditions):
    return session.scalar(select_current(model.id).where(*conditions).limit(1)) is not None


def reject_dependency(found, message):
    if found:
        raise DomainError('operation_has_followup', message, status_code=409)


def check_order_issues(session, order_id):
    reject_dependency(exists(session, DepartmentWorkOrderMovement,
        DepartmentWorkOrderMovement.work_order_id == order_id, DepartmentWorkOrderMovement.direction == 'issue'),
        '此工单已有出料，请先撤回工单的后续出料')


def check_dependencies(session, kind, row, order, *, lock_lots=True):
    if kind == 'purchase':
        reject_dependency(exists(session, PurchaseReceipt, PurchaseReceipt.purchase_order_id == row.id), '采购已登记到料，请先撤回采购到料')
    elif kind == 'purchase_receipt':
        check_order_issues(session, order.id)
    elif kind == 'movement' and row.direction == 'issue':
        tickets = select(DepartmentHandoffTicket.id).where(DepartmentHandoffTicket.issue_movement_id == row.id)
        reject_dependency(exists(session, DepartmentWorkOrderMovement, DepartmentWorkOrderMovement.ticket_id.in_(tickets))
            or exists(session, QcInspection, QcInspection.source_ticket_id.in_(tickets)),
            '下游已登记到料或质检，请先由下游撤回')
    elif kind == 'movement':
        check_order_issues(session, order.id)
        reject_dependency(exists(session, OutsourceDispatch, OutsourceDispatch.receipt_id == row.id), '此笔到料已外发，请先撤回外发')
        statement = select(WarehouseLot).where(WarehouseLot.receipt_movement_id == row.id).order_by(WarehouseLot.id)
        if lock_lots:
            statement = statement.with_for_update()
        lots = list(session.scalars(statement))
        reject_dependency(session.scalar(select_current(WarehouseAllocation.pick_id).where(
            WarehouseAllocation.lot_id.in_({lot.id for lot in lots})).limit(1)) is not None,
            '此批仓库物料已出料，请先撤回仓库出料')
    elif kind == 'inspection':
        check_order_issues(session, order.id)
        tickets = select(QcReworkTicket.id).where(QcReworkTicket.inspection_id == row.id)
        reject_dependency(exists(session, QcReworkEvent, QcReworkEvent.ticket_id.in_(tickets)), '返修已接收，请先撤回后续返修操作')
    elif kind == 'rework':
        if row.action == 'return':
            reject_dependency(exists(session, QcInspection, QcInspection.source_return_id == row.id), 'QC已复检，请先撤回复检')
        else:
            reject_dependency(exists(session, QcReworkEvent, QcReworkEvent.ticket_id == row.ticket_id,
                QcReworkEvent.action == 'return'), '返修已回交QC，请先撤回回交')
    elif kind == 'warehouse':
        reject_dependency(exists(session, DepartmentWorkOrderMovement, DepartmentWorkOrderMovement.warehouse_pick_id == row.id)
            or exists(session, QcInspection, QcInspection.source_pick_id == row.id), '下游已接收或质检，请先由下游撤回')
    elif kind == 'outsource':
        reject_dependency(exists(session, OutsourceReturn, OutsourceReturn.dispatch_id == row.id), '已登记厂商回料，请先撤回回料')
    elif kind == 'outsource_return':
        check_order_issues(session, order.id)


def revocation_blocker(session, kind, row, order, *, department_scope, plan_status):
    if department_scope is None:
        return '业务账号只读，不能撤回'
    if row.revoked_at is not None:
        return '操作已撤回'
    if kind in {'purchase', 'purchase_receipt'} and department_scope != 'warehouse':
        return '采购业务仅仓库可撤回'
    if kind in {'movement', 'rework'} and department_scope == 'purchase':
        return '外购节点操作由仓库负责'
    if plan_status != 'confirmed':
        return '仅已确认计划允许撤回操作'
    try:
        check_dependencies(session, kind, row, order, lock_lots=False)
    except DomainError as error:
        if error.code != 'operation_has_followup':
            raise
        return error.message
    return None


def revoke_operation(kind, operation_id, payload, *, department_scope, actor_user_id):
    if department_scope is None:
        raise DomainError('revoke_operator_required', '仅所属部门可撤回本部门操作，业务账号只读', status_code=403)
    if not payload.reason.strip():
        raise DomainError('revoke_reason_required', '请填写撤回原因', path='reason')
    model = OPERATION_MODELS[kind]
    with SessionLocal.begin() as session:
        row = session.get(model, operation_id)
        if row is None:
            raise DomainError('operation_missing', '操作记录不存在', status_code=404)
        order_id, required_department = operation_source(session, kind, row)
        order = load_scoped_order(session, order_id, None if required_department else department_scope)
        if required_department is not None and department_scope != required_department:
            raise DomainError('revoke_department_denied', '只能撤回本部门操作', status_code=403)
        plan = load_plan(session, order.production_plan_id, for_update=True)
        row = session.scalar(select(model).where(model.id == operation_id).with_for_update()
            .execution_options(populate_existing=True))
        if row.revoked_at is not None:
            return {'id': row.id}
        if plan.status != 'confirmed':
            raise DomainError('revoke_plan_closed', '仅已确认计划允许撤回操作', status_code=409)
        check_dependencies(session, kind, row, order)
        row.revoked_at, row.revoked_by, row.revoke_reason = utc_now(), actor_user_id, payload.reason
        session.flush()
        return {'id': row.id}
