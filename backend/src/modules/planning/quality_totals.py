from sqlalchemy import func

from modules.planning.current_records import select_current
from modules.planning.persistence import QcInspection


def inspection_totals(session, order_ids):
    if not order_ids:
        return {}
    return {order_id: (int(good), int(scrap), int(rework)) for order_id, good, scrap, rework in session.execute(
        select_current(QcInspection.work_order_id, func.sum(QcInspection.good_quantity),
               func.sum(QcInspection.scrap_quantity), func.sum(QcInspection.rework_quantity))
        .where(QcInspection.work_order_id.in_(order_ids)).group_by(QcInspection.work_order_id))}
