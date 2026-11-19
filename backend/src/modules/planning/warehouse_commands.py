"""Warehouse-only FIFO dispatch creating a pending downstream handoff."""

from database import SessionLocal
from domain.warehouse import material_stock_key
from schemas.warehouse import WarehouseDispatchCreate
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from modules.errors import DomainError
from modules.organization.read_api import is_warehouse
from modules.planning.handoffs import order_context
from modules.planning.persistence import (
    DepartmentWorkOrder,
    WarehouseAllocation,
    WarehouseLot,
    WarehousePick,
)
from modules.planning.queries import load_plan
from modules.planning.warehouse_stock import warehouse_source_keys
from modules.planning.work_order_access import load_scoped_order


def validate_dispatch_source(session, order, warehouse_order_id):
    source = session.get(DepartmentWorkOrder, warehouse_order_id)
    context, key = order_context(session, order)
    if is_warehouse(context['departments'][order.department_node_id]):
        raise DomainError('warehouse_dispatch_to_self', '共享仓库不能向自身出料', status_code=403)
    if (source is None or (source.production_plan_id, source.product_id) != (order.production_plan_id, order.product_id)
        or (source.material_node_id, source.department_node_id) not in warehouse_source_keys(context, key)):
        raise DomainError('warehouse_route_denied', '仅可从此工单的直接仓库前序出料', status_code=403)
    return source, context


def lock_available_lots(session, product_id, material_key):
    allocated = select(func.coalesce(func.sum(WarehouseAllocation.quantity), 0)).where(
        WarehouseAllocation.lot_id == WarehouseLot.id).scalar_subquery()
    lots = list(session.scalars(select(WarehouseLot).where(WarehouseLot.product_id == product_id,
        WarehouseLot.material_key == material_key, WarehouseLot.quantity > allocated)
        .order_by(WarehouseLot.id).with_for_update()))
    totals = dict(session.execute(select(WarehouseAllocation.lot_id, func.sum(WarehouseAllocation.quantity))
        .where(WarehouseAllocation.lot_id.in_({lot.id for lot in lots})).group_by(WarehouseAllocation.lot_id)).all())
    return [(lot, lot.quantity - int(totals.get(lot.id, 0))) for lot in lots]


def allocate_lots(session, pick, lots):
    remaining = pick.quantity
    for lot, available in lots:
        quantity = min(remaining, available)
        if quantity > 0:
            session.add(WarehouseAllocation(pick_id=pick.id, lot_id=lot.id, quantity=quantity))
            remaining -= quantity
        if remaining == 0:
            break


def dispatch_warehouse(order_id: int, payload: WarehouseDispatchCreate, *, department_scope, actor_user_id):
    if not is_warehouse(department_scope):
        raise DomainError('warehouse_dispatch_operator', '仅仓库账号可执行仓库出料，下游只能查看库存', status_code=403)
    try:
        with SessionLocal.begin() as session:
            order = load_scoped_order(session, order_id, department_scope=None)
            plan = load_plan(session, order.production_plan_id, for_update=True)
            order = load_scoped_order(session, order_id, department_scope=None)
            previous = session.scalar(select(WarehousePick).where(WarehousePick.request_id == payload.request_id))
            if previous is not None:
                check_dispatch_retry(previous, order_id, payload, actor_user_id)
                return {'id': previous.id}
            if plan.status != 'confirmed':
                raise DomainError('warehouse_plan_closed', '仅已确认计划允许接收仓库出料', status_code=409)
            source, context = validate_dispatch_source(session, order, payload.warehouse_order_id)
            key = material_stock_key(context, source.material_node_id)
            if (payload.product_id, payload.material_key) != (order.product_id, key):
                raise DomainError('warehouse_dispatch_material', '所选库存与目标工单物料不一致', status_code=403)
            lots = lock_available_lots(session, order.product_id, key)
            if sum(available for lot, available in lots) < payload.quantity:
                raise DomainError('warehouse_stock_insufficient', '仓库库存不足，请刷新库存后重试', status_code=409)
            pick = WarehousePick(target_order_id=order.id, route_warehouse_order_id=source.id, product_id=order.product_id,
                material_key=key, quantity=payload.quantity, request_id=payload.request_id,
                actor_user_id=actor_user_id, note=payload.note)
            session.add(pick)
            session.flush()
            allocate_lots(session, pick, lots)
            session.flush()
            return {'id': pick.id}
    except IntegrityError as exc:
        raise DomainError('warehouse_dispatch_conflict', '仓库出料或提交标识冲突，请刷新后重试', status_code=409) from exc


def check_dispatch_retry(previous, order_id, payload, actor_user_id):
    if (previous.target_order_id, previous.route_warehouse_order_id, previous.quantity, previous.note, previous.actor_user_id, previous.product_id, previous.material_key) != (
        order_id, payload.warehouse_order_id, payload.quantity, payload.note, actor_user_id, payload.product_id, payload.material_key):
        raise DomainError('warehouse_dispatch_request_conflict', '该提交标识已用于其他出料', status_code=409)
