"""Warehouse-only order and route choices for a selected physical SKU."""

from database import SessionLocal
from domain.warehouse import material_stock_key
from sqlalchemy import select

from modules.errors import DomainError
from modules.organization.read_api import department_names, is_warehouse
from modules.planning.current_records import select_current
from modules.planning.handoffs import order_context
from modules.planning.persistence import (
    DepartmentWorkOrder,
    PlanProductRoute,
    ProductionPlan,
    ProductionPlanItem,
    WarehouseLot,
)
from modules.planning.queries import load_plan
from modules.planning.snapshots import material_number
from modules.planning.warehouse_stock import pool_quantities


def dispatch_lot(session, lot_id, department_scope):
    if not is_warehouse(department_scope):
        raise DomainError('warehouse_dispatch_scope', '仅仓库账号可选择出料目标', status_code=403)
    lot = session.scalar(select_current(WarehouseLot).where(WarehouseLot.id == lot_id))
    if lot is None:
        raise DomainError('warehouse_stock_missing', '库存批次不存在', status_code=404)
    return lot


def dispatch_plans(lot_id, keyword, *, department_scope):
    with SessionLocal() as session:
        lot = dispatch_lot(session, lot_id, department_scope)
        warehouse_route = select(PlanProductRoute.product_id).where(
            PlanProductRoute.production_plan_id == ProductionPlan.id,
            PlanProductRoute.product_id == lot.product_id,
            PlanProductRoute.department_code == 'warehouse').exists()
        statement = select(ProductionPlan.id, ProductionPlan.order_no).join(
            ProductionPlanItem, ProductionPlanItem.production_plan_id == ProductionPlan.id).where(
            ProductionPlan.status == 'confirmed', ProductionPlanItem.product_id == lot.product_id, warehouse_route)
        if keyword:
            statement = statement.where(ProductionPlan.order_no.ilike(f'%{keyword.strip()}%'))
        return [{'id': plan_id, 'order_no': order_no} for plan_id, order_no in session.execute(
            statement.order_by(ProductionPlan.id.desc()).limit(50))]


def dispatch_targets(lot_id, plan_id, *, department_scope):
    with SessionLocal() as session:
        lot = dispatch_lot(session, lot_id, department_scope)
        plan = load_plan(session, plan_id)
        if plan.status != 'confirmed':
            raise DomainError('warehouse_dispatch_plan_closed', '目标计划必须为已确认状态', status_code=409)
        orders = list(session.scalars(select(DepartmentWorkOrder).where(
            DepartmentWorkOrder.production_plan_id == plan_id, DepartmentWorkOrder.product_id == lot.product_id)
            .order_by(DepartmentWorkOrder.id)))
        if not orders:
            return []
        context, _ = order_context(session, orders[0])
        by_key = {(order.material_node_id, order.department_node_id): order for order in orders}
        names = department_names(session)
        quantity = pool_quantities(session, lot.product_id, {lot.material_key}).get(lot.material_key, 0)
        targets = eligible_targets(orders, context, by_key, lot.material_key)
        return [{'target_order_id': target.id, 'warehouse_order_id': source.id,
            'department': names[context['departments'][target.department_node_id]],
            'material': f"{material_number(context, source.material_node_id)} · {context['materials'][source.material_node_id]}",
            'available_quantity': str(quantity)} for target, source in targets.values()]


def eligible_targets(orders, context, by_key, material_key):
    targets = {}
    for source in orders:
        if not is_warehouse(context['departments'][source.department_node_id]):
            continue
        if material_stock_key(context, source.material_node_id) != material_key:
            continue
        for target_key in sorted(context['routes'].successors[(source.material_node_id, source.department_node_id)]):
            target = by_key.get(target_key)
            if target is None:
                raise DomainError('warehouse_dispatch_target_missing', '下游工单缺失，请业务部核对计划', status_code=409)
            if not is_warehouse(context['departments'][target.department_node_id]):
                targets.setdefault(target.id, (target, source))
    return targets
