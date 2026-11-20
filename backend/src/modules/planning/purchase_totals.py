from sqlalchemy import func

from modules.planning.current_records import select_current
from modules.planning.persistence import PurchaseOrder, PurchaseReceipt


def purchase_received_totals(session, order_ids):
    if not order_ids:
        return {}
    return {order_id: int(quantity) for order_id, quantity in session.execute(
        select_current(PurchaseOrder.work_order_id, func.sum(PurchaseReceipt.quantity))
        .select_from(PurchaseReceipt).join(PurchaseOrder, PurchaseOrder.id == PurchaseReceipt.purchase_order_id)
        .where(PurchaseOrder.work_order_id.in_(order_ids)).group_by(PurchaseOrder.work_order_id))}
