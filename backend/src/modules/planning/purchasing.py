"""Warehouse-managed purchases attached to unchanged purchase route nodes."""

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.planning.current_records import require_effective, select_current
from modules.planning.persistence import PurchaseOrder, PurchaseReceipt
from modules.planning.queries import load_plan
from modules.planning.work_order_access import load_scoped_order
from modules.planning.work_orders import list_work_orders


def require_purchase_scope(department_scope, *, writing=False):
    if department_scope != 'warehouse' and (writing or department_scope is not None):
        raise DomainError('purchase_operator_denied', '采购、采购到料及外购出料由仓库负责，业务只读', status_code=403)


def locked_purchase_order(session, work_order_id):
    order = load_scoped_order(session, work_order_id, 'purchase')
    plan = load_plan(session, order.production_plan_id, for_update=True)
    return order, plan


def require_open_purchase(plan):
    if plan.status != 'confirmed':
        raise DomainError('purchase_plan_closed', '仅已确认计划可采购及登记到料', status_code=409)


def check_purchase_retry(previous, values):
    require_effective(previous)
    if any(getattr(previous, key) != value for key, value in values.items()):
        raise DomainError('purchase_request_conflict', '此提交标识已用于其他采购操作', status_code=409)
    return {'id': previous.id}


def create_purchase(work_order_id, payload, *, department_scope, actor_user_id):
    require_purchase_scope(department_scope, writing=True)
    values = payload.model_dump() | {'work_order_id': work_order_id, 'actor_user_id': actor_user_id}
    try:
        with SessionLocal.begin() as session:
            _, plan = locked_purchase_order(session, work_order_id)
            previous = session.scalar(select(PurchaseOrder).where(PurchaseOrder.request_id == payload.request_id))
            if previous is not None:
                return check_purchase_retry(previous, values)
            require_open_purchase(plan)
            row = PurchaseOrder(**values)
            session.add(row)
            session.flush()
            return {'id': row.id}
    except IntegrityError as exc:
        raise DomainError('purchase_conflict', '采购提交冲突，请刷新后重试', status_code=409) from exc


def receive_purchase(purchase_id, payload, *, department_scope, actor_user_id):
    require_purchase_scope(department_scope, writing=True)
    values = payload.model_dump() | {'purchase_order_id': purchase_id, 'actor_user_id': actor_user_id}
    try:
        with SessionLocal.begin() as session:
            purchase = session.get(PurchaseOrder, purchase_id)
            if purchase is None:
                raise DomainError('purchase_missing', '采购记录不存在', status_code=404)
            _, plan = locked_purchase_order(session, purchase.work_order_id)
            purchase = session.scalar(select(PurchaseOrder).where(PurchaseOrder.id == purchase_id).with_for_update()
                .execution_options(populate_existing=True))
            require_effective(purchase)
            previous = session.scalar(select(PurchaseReceipt).where(PurchaseReceipt.request_id == payload.request_id))
            if previous is not None:
                return check_purchase_retry(previous, values)
            require_open_purchase(plan)
            if session.scalar(select_current(PurchaseReceipt.id).where(PurchaseReceipt.purchase_order_id == purchase_id)) is not None:
                raise DomainError('purchase_already_received', '此采购记录已登记到料，不能重复登记', status_code=409)
            if payload.quantity > purchase.quantity:
                raise DomainError('purchase_receipt_exceeded', '到料不能超过采购数量', path='quantity')
            if payload.quantity < purchase.quantity and not payload.note.strip():
                raise DomainError('purchase_receipt_note_required', '到料少于采购数量时必须填写备注', path='note')
            row = PurchaseReceipt(**values)
            session.add(row)
            session.flush()
            return {'id': row.id}
    except IntegrityError as exc:
        raise DomainError('purchase_receipt_conflict', '采购到料或提交标识冲突，请刷新后重试', status_code=409) from exc


def purchase_work_orders(page, page_size, *, department_scope):
    require_purchase_scope(department_scope)
    data, total = list_work_orders(page, page_size, department_scope=None, department_code='purchase')
    with SessionLocal() as session:
        purchases = list(session.scalars(select_current(PurchaseOrder).where(
            PurchaseOrder.work_order_id.in_({row['id'] for row in data})).order_by(PurchaseOrder.id))) if data else []
        received = {row.purchase_order_id: row for row in session.scalars(select_current(PurchaseReceipt).where(
            PurchaseReceipt.purchase_order_id.in_({row.id for row in purchases})))} if purchases else {}
        users = usernames_by_ids(session, {row.actor_user_id for row in purchases})
        by_order = {}
        for row in purchases:
            receipt = received.get(row.id)
            by_order.setdefault(row.work_order_id, []).append({'id': row.id, 'quantity': str(row.quantity),
                'note': row.note, 'actor_username': users[row.actor_user_id],
                'created_at': row.created_at.astimezone(BUSINESS_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'),
                'received': receipt is not None, 'received_quantity': str(receipt.quantity if receipt else 0)})
        for row in data:
            row['purchases'] = by_order.get(row['id'], [])
            row['can_issue'] = department_scope == 'warehouse'
        return data, total
