"""Physical lots and precise shared-pool balances."""

from domain.warehouse import material_stock_key
from sqlalchemy import func

from modules.errors import DomainError
from modules.organization.read_api import is_warehouse
from modules.planning.current_records import select_current
from modules.planning.persistence import WarehouseAllocation, WarehouseLot


def warehouse_source_keys(context, target_key):
    return {key for key, successors in context['routes'].successors.items()
            if key != target_key and target_key in successors and is_warehouse(context['departments'][key[1]])}


def create_warehouse_lot(session, order, movement, context):
    if movement.input_material_node_id != order.material_node_id:
        raise DomainError('warehouse_whole_material_required', '仓库入库必须与工单物料一致，装配体须整套入库')
    session.add(WarehouseLot(warehouse_order_id=order.id, receipt_movement_id=movement.id,
        product_id=order.product_id, material_key=material_stock_key(context, order.material_node_id), quantity=movement.quantity))
    session.flush()


def lot_balances():
    allocated = (select_current(WarehouseAllocation.lot_id, func.sum(WarehouseAllocation.quantity).label('quantity'))
                 .group_by(WarehouseAllocation.lot_id).subquery())
    return (select_current(WarehouseLot.id.label('lot_id'), WarehouseLot.warehouse_order_id.label('order_id'),
        WarehouseLot.product_id, WarehouseLot.material_key, WarehouseLot.created_at.label('arrived_at'),
        (WarehouseLot.quantity - func.coalesce(allocated.c.quantity, 0)).label('available'))
        .select_from(WarehouseLot).outerjoin(allocated, allocated.c.lot_id == WarehouseLot.id)).subquery()


def pool_quantities(session, product_id, material_keys):
    if not material_keys:
        return {}
    balances = lot_balances()
    return {key: int(quantity) for key, quantity in session.execute(select_current(balances.c.material_key,
        func.sum(balances.c.available)).where(balances.c.product_id == product_id,
        balances.c.material_key.in_(material_keys)).group_by(balances.c.material_key))}


def warehouse_dispatched(session, order_ids):
    if not order_ids:
        return {}
    return {order_id: int(quantity) for order_id, quantity in session.execute(
        select_current(WarehouseLot.warehouse_order_id, func.sum(WarehouseAllocation.quantity))
        .join(WarehouseAllocation, WarehouseAllocation.lot_id == WarehouseLot.id)
        .where(WarehouseLot.warehouse_order_id.in_(order_ids)).group_by(WarehouseLot.warehouse_order_id))}
