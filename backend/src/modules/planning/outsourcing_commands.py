"""External processing of received material, serialized by its parent plan."""

from database import SessionLocal
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from modules.errors import DomainError
from modules.planning.current_records import require_effective, select_current
from modules.planning.persistence import (
    DepartmentWorkOrderMovement,
    OutsourceDispatch,
    OutsourceReturn,
)
from modules.planning.queries import load_plan
from modules.planning.work_order_access import load_scoped_order


def require_outsource_operator(department_scope):
    if department_scope != 'outsource':
        raise DomainError('outsource_operator_denied', '仅委外部门可登记外发和回料', status_code=403)


def lock_receipt(session, receipt_id):
    receipt = session.scalar(select_current(DepartmentWorkOrderMovement).where(DepartmentWorkOrderMovement.id == receipt_id))
    if receipt is None or receipt.direction != 'receipt':
        raise DomainError('outsource_receipt_missing', '请选择委外部门已登记的交接到料', status_code=404)
    order = load_scoped_order(session, receipt.work_order_id, 'outsource')
    plan = load_plan(session, order.production_plan_id, for_update=True)
    receipt = session.scalar(select_current(DepartmentWorkOrderMovement).where(
        DepartmentWorkOrderMovement.id == receipt_id).with_for_update())
    if receipt is None:
        raise DomainError('outsource_receipt_revoked', '此笔到料已撤回，请刷新', status_code=409)
    return receipt, plan


def check_retry(previous, expected):
    if any(getattr(previous, key) != value for key, value in expected.items()):
        raise DomainError('outsource_request_conflict', '提交标识已用于其他委外登记，请重新打开窗口', status_code=409)
    return {'id': previous.id}


def require_open_plan(plan):
    if plan.status != 'confirmed':
        raise DomainError('outsource_plan_closed', '仅已确认计划可登记外发和回料', status_code=409)


def dispatch_outsource(payload, *, department_scope, actor_user_id):
    require_outsource_operator(department_scope)
    if not payload.vendor.strip():
        raise DomainError('outsource_vendor_required', '请填写加工厂商', path='vendor')
    values = payload.model_dump() | {'actor_user_id': actor_user_id}
    try:
        with SessionLocal.begin() as session:
            receipt, plan = lock_receipt(session, payload.receipt_id)
            previous = session.scalar(select(OutsourceDispatch).where(OutsourceDispatch.request_id == payload.request_id))
            if previous is not None:
                require_effective(previous)
                return check_retry(previous, values)
            require_open_plan(plan)
            dispatched = session.scalar(select_current(func.coalesce(func.sum(OutsourceDispatch.quantity), 0)).where(
                OutsourceDispatch.receipt_id == receipt.id))
            if payload.quantity > receipt.quantity - int(dispatched):
                raise DomainError('outsource_dispatch_exceeded', '外发数量不能超过此笔到料尚未外发的数量', path='quantity')
            row = OutsourceDispatch(**values)
            session.add(row)
            session.flush()
            return {'id': row.id}
    except IntegrityError as exc:
        raise DomainError('outsource_dispatch_conflict', '外发数量或提交标识冲突，请刷新后重试', status_code=409) from exc


def return_outsource(dispatch_id, payload, *, department_scope, actor_user_id):
    require_outsource_operator(department_scope)
    values = payload.model_dump() | {'dispatch_id': dispatch_id, 'actor_user_id': actor_user_id}
    try:
        with SessionLocal.begin() as session:
            dispatch = session.scalar(select_current(OutsourceDispatch).where(OutsourceDispatch.id == dispatch_id))
            if dispatch is None:
                raise DomainError('outsource_dispatch_missing', '外发记录不存在', status_code=404)
            _, plan = lock_receipt(session, dispatch.receipt_id)
            dispatch = session.scalar(select_current(OutsourceDispatch).where(
                OutsourceDispatch.id == dispatch_id).with_for_update())
            if dispatch is None:
                raise DomainError('outsource_dispatch_revoked', '外发已撤回，请刷新', status_code=409)
            previous = session.scalar(select(OutsourceReturn).where(OutsourceReturn.request_id == payload.request_id))
            if previous is not None:
                require_effective(previous)
                return check_retry(previous, values)
            require_open_plan(plan)
            returned = session.scalar(select_current(func.coalesce(func.sum(OutsourceReturn.quantity), 0)).where(
                OutsourceReturn.dispatch_id == dispatch.id))
            if payload.quantity > dispatch.quantity - int(returned):
                raise DomainError('outsource_return_exceeded', '回料数量不能超过此外发单尚未回料的数量', path='quantity')
            row = OutsourceReturn(**values)
            session.add(row)
            session.flush()
            return {'id': row.id}
    except IntegrityError as exc:
        raise DomainError('outsource_return_conflict', '回料数量或提交标识冲突，请刷新后重试', status_code=409) from exc
