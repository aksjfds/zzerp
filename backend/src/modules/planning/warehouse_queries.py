from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE, business_iso
from domain.warehouse import material_stock_key
from sqlalchemy import func, select, tuple_

from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.organization.read_api import (
    allows_pick_history,
    department_names,
    is_warehouse,
)
from modules.planning.persistence import (
    DepartmentWorkOrder,
    ProductionPlan,
    WarehouseAllocation,
    WarehouseLot,
    WarehousePick,
)
from modules.planning.snapshots import (
    handoff_contexts,
    item_key,
    material_labels,
    order_department_filter,
    route_key,
    route_references,
)
from modules.planning.warehouse_stock import (
    lot_balances,
    warehouse_source_keys,
)


def department_warehouse_stocks(page, page_size, *, department_scope, department_code=None):
    if department_scope is not None and department_code not in {None, department_scope}:
        raise DomainError('warehouse_stock_department_denied', '不能查看其他部门关联库存', status_code=403)
    scope = department_scope or department_code
    if not scope:
        raise DomainError('warehouse_stock_department_required', '请选择库存查看部门')
    if is_warehouse(scope):
        return warehouse_stocks(page, page_size, department_scope=department_scope)
    with SessionLocal() as session:
        orders = list(session.scalars(select(DepartmentWorkOrder).join(
            ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id).where(
            ProductionPlan.status != 'draft', ProductionPlan.confirmed_at.is_not(None), order_department_filter(scope))))
        contexts = handoff_contexts(session, {item_key(order) for order in orders})
        skus = set()
        for order in orders:
            context = contexts[item_key(order)]
            for source in warehouse_source_keys(context, (order.material_node_id, order.department_node_id)):
                skus.add((order.product_id, material_stock_key(context, source[0])))
        if not skus:
            return [], 0
        balances = lot_balances()
        statement = select(balances).where(balances.c.available > 0,
            tuple_(balances.c.product_id, balances.c.material_key).in_(skus))
        return stock_page(session, statement, balances, page, page_size)


def warehouse_stocks(page, page_size, *, department_scope):
    if department_scope is not None and not is_warehouse(department_scope):
        raise DomainError('warehouse_stock_scope', '请从本人部门的仓库库存页签查看库存', status_code=403)
    with SessionLocal() as session:
        balances = lot_balances()
        statement = select(balances).where(balances.c.available > 0)
        return stock_page(session, statement, balances, page, page_size)


def stock_page(session, statement, balances, page, page_size):
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.execute(statement.order_by(balances.c.arrived_at.desc(), balances.c.lot_id.desc())
                           .offset((page - 1) * page_size).limit(page_size)).all()
    labels = material_labels(session, {row.order_id for row in rows})
    return [{'id': row.lot_id, 'product_id': row.product_id, 'material_key': row.material_key,
        'product': f"{labels[row.order_id]['factory_code']} · {labels[row.order_id]['product_name']}",
        'material': f"{labels[row.order_id]['material_no']} · {labels[row.order_id]['material_name']}",
        'available_quantity': str(int(row.available)),
        'arrival_date': row.arrived_at.astimezone(BUSINESS_TIMEZONE).date().isoformat()} for row in rows], total


def warehouse_picks(page, page_size, *, department_scope, pick_id=None):
    if department_scope is not None and not allows_pick_history(department_scope):
        raise DomainError('warehouse_pick_history_scope', '当前账号不提供领料记录页面', status_code=403)
    with SessionLocal() as session:
        statement = select(WarehousePick, DepartmentWorkOrder, ProductionPlan).select_from(WarehousePick)\
            .join(DepartmentWorkOrder, DepartmentWorkOrder.id == WarehousePick.target_order_id)\
            .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
        if department_scope is not None and not is_warehouse(department_scope):
            statement = statement.where(order_department_filter(department_scope))
        if pick_id is not None:
            statement = statement.where(WarehousePick.id == pick_id)
        total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = session.execute(statement.order_by(WarehousePick.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        labels = material_labels(session, {pick.route_warehouse_order_id for pick, order, plan in rows})
        refs = route_references(session, route_keys={route_key(order) for pick, order, plan in rows})
        names = department_names(session)
        users = usernames_by_ids(session, {pick.actor_user_id for pick, order, plan in rows})
        sources = pick_sources(session, {pick.id for pick, order, plan in rows})
        return [{'id': pick.id, 'order_no': plan.order_no,
            'product': f"{labels[pick.route_warehouse_order_id]['factory_code']} · {labels[pick.route_warehouse_order_id]['product_name']}",
            'material': f"{labels[pick.route_warehouse_order_id]['material_no']} · {labels[pick.route_warehouse_order_id]['material_name']}",
            'quantity': str(pick.quantity), 'department': names[refs[route_key(order)].department_code],
            'actor_username': users[pick.actor_user_id], 'created_at': business_iso(pick.created_at),
            'sources': '；'.join(sources.get(pick.id, [])), 'note': pick.note} for pick, order, plan in rows], total


def pick_sources(session, pick_ids):
    rows = session.execute(select(WarehouseAllocation.pick_id, ProductionPlan.order_no, WarehouseAllocation.quantity)
        .select_from(WarehouseAllocation).join(WarehouseLot, WarehouseLot.id == WarehouseAllocation.lot_id)
        .join(DepartmentWorkOrder, DepartmentWorkOrder.id == WarehouseLot.warehouse_order_id)
        .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
        .where(WarehouseAllocation.pick_id.in_(pick_ids)).order_by(WarehouseAllocation.lot_id))
    result = {}
    for pick_id, order_no, quantity in rows:
        result.setdefault(pick_id, []).append(f'{order_no} · {quantity}')
    return result
