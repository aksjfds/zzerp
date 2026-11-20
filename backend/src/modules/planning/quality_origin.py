"""Resolve the immutable first sender of a QC batch through all rework rounds."""


from sqlalchemy.orm import aliased

from modules.errors import DomainError
from modules.planning.current_records import select_current
from modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    QcInspection,
    QcReworkEvent,
    QcReworkTicket,
    WarehousePick,
)
from modules.planning.snapshots import route_key, route_references


def batch_origin(session, kind, source_id):
    if kind == 'return':
        seed = select_current(QcReworkTicket.inspection_id).join(QcReworkEvent,
            QcReworkEvent.ticket_id == QcReworkTicket.id).where(QcReworkEvent.id == source_id, QcReworkEvent.action == 'return').scalar_subquery()
        chain = select_current(QcInspection.id, QcInspection.source_ticket_id, QcInspection.source_pick_id,
            QcInspection.source_return_id).where(QcInspection.id == seed).cte('qc_origin', recursive=True)
        parent = aliased(QcInspection)
        chain = chain.union_all(select_current(parent.id, parent.source_ticket_id, parent.source_pick_id, parent.source_return_id)
            .select_from(chain).join(QcReworkEvent, QcReworkEvent.id == chain.c.source_return_id)
            .join(QcReworkTicket, QcReworkTicket.id == QcReworkEvent.ticket_id)
            .join(parent, parent.id == QcReworkTicket.inspection_id))
        root = session.execute(select_current(chain).where(chain.c.source_return_id.is_(None))).first()
        if root is None:
            raise DomainError('qc_origin_missing', '原始来料不存在', status_code=404)
        kind, source_id = ('handoff', root.source_ticket_id) if root.source_ticket_id is not None else ('warehouse', root.source_pick_id)
    worker = ''
    if kind == 'handoff':
        issue = session.scalar(select_current(DepartmentWorkOrderMovement).join(DepartmentHandoffTicket,
            DepartmentHandoffTicket.issue_movement_id == DepartmentWorkOrderMovement.id).where(DepartmentHandoffTicket.id == source_id))
        if issue is None:
            raise DomainError('qc_origin_missing', '原始交接票不存在', status_code=404)
        order_id, worker = issue.work_order_id, issue.worker_name
    else:
        pick = session.scalar(select_current(WarehousePick).where(WarehousePick.id == source_id))
        if pick is None:
            raise DomainError('qc_origin_missing', '原始仓库票不存在', status_code=404)
        order_id = pick.route_warehouse_order_id
    order = session.get(DepartmentWorkOrder, order_id)
    ref = route_references(session, route_keys={route_key(order)})[route_key(order)]
    return {'department_code': ref.department_code, 'worker_name': worker}
