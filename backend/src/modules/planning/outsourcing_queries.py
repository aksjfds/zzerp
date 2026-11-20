"""Read received batches with their external processing and return evidence."""

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE
from sqlalchemy import func

from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.planning.current_records import select_current
from modules.planning.material_movements import serialize_movements
from modules.planning.persistence import (
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    OutsourceDispatch,
    OutsourceReturn,
)
from modules.planning.quality_queries import order_labels
from modules.planning.snapshots import order_department_filter


def event_row(row, users):
    return {'id': row.id, 'quantity': str(row.quantity), 'note': row.note,
            'actor_username': users[row.actor_user_id],
            'created_at': row.created_at.astimezone(BUSINESS_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}


def outsource_receipts(page, page_size, *, department_scope, receipt_id=None):
    if department_scope not in {None, 'outsource'}:
        raise DomainError('outsource_view_denied', '仅委外部门或业务可查看外发加工', status_code=403)
    with SessionLocal() as session:
        query = select_current(DepartmentWorkOrderMovement).join(DepartmentWorkOrder,
            DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id).where(
                DepartmentWorkOrderMovement.direction == 'receipt', order_department_filter('outsource'))
        if receipt_id is not None:
            query = query.where(DepartmentWorkOrderMovement.id == receipt_id)
        total = session.scalar(select_current(func.count()).select_from(query.subquery())) or 0
        receipts = list(session.scalars(query.order_by(DepartmentWorkOrderMovement.id.desc())
            .offset((page-1)*page_size).limit(page_size)))
        if not receipts:
            return [], total
        dispatches = list(session.scalars(select_current(OutsourceDispatch).where(
            OutsourceDispatch.receipt_id.in_({row.id for row in receipts})).order_by(OutsourceDispatch.id)))
        returns = list(session.scalars(select_current(OutsourceReturn).where(
            OutsourceReturn.dispatch_id.in_({row.id for row in dispatches})).order_by(OutsourceReturn.id))) if dispatches else []
        users = usernames_by_ids(session, {row.actor_user_id for row in dispatches + returns})
        labels = order_labels(session, {row.work_order_id for row in receipts})
        materials = {row['id']: row for row in serialize_movements(session, receipts)}
        by_dispatch, by_receipt = {}, {}
        for row in returns:
            by_dispatch.setdefault(row.dispatch_id, []).append(event_row(row, users))
        for row in dispatches:
            events = by_dispatch.get(row.id, [])
            by_receipt.setdefault(row.receipt_id, []).append(event_row(row, users) | {
                'process': row.process, 'vendor': row.vendor, 'returns': events,
                'returned_quantity': str(sum(int(event['quantity']) for event in events))})
        result = []
        for row in receipts:
            label, material = labels[row.work_order_id], materials[row.id]
            batches = by_receipt.get(row.id, [])
            result.append({'id': row.id, 'order_no': label['order_no'], 'product': label['product'],
                'material': f"{material['material_no']} · {material['material_name']}", 'plan_status': label['plan_status'],
                'quantity': str(row.quantity), 'created_at': material['created_at'], 'dispatches': batches,
                'dispatched_quantity': str(sum(int(batch['quantity']) for batch in batches))})
        return result, total
