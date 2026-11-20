"""Worker-attributed piecework quantities and complete QC evidence."""

from database import SessionLocal
from sqlalchemy import func

from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.organization.read_api import department_names
from modules.planning.current_records import select_current
from modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrderMovement,
    QcInspection,
)
from modules.planning.quality_queries import order_labels
from modules.planning.quality_timeline import batch_history, build_batches, event_time


def ticket_result(issue, ticket_id, batch, label):
    inspections = [event['inspection'] for event in batch['events'] if event['inspection']] if batch else []
    first_only = any(record['repair_kind'] == 'cross' for record in inspections)
    counted = inspections[:1] if first_only else inspections
    good = sum(int(record['good_quantity']) for record in counted)
    scrap = sum(int(record['scrap_quantity']) for record in counted)
    return {'id': ticket_id, 'ticket_no': f'JT-{ticket_id:08d}', 'quantity': str(issue.quantity),
        'piecework_process': issue.piecework_process,
        'good_quantity': str(good), 'scrap_quantity': str(scrap), 'unsettled_quantity': str(issue.quantity - good - scrap),
        'first_only': first_only, 'created_at': event_time(issue.created_at), 'note': issue.note,
        'order_no': label['order_no'], 'product': label['product'], 'material': label['material'],
        'events': batch['events'] if batch else []}


def worker_piecework(page, page_size, worker_name, *, department_scope):
    if department_scope not in {None, 'grinding'}:
        raise DomainError('worker_piecework_denied', '仅磨房或业务可查看工人计件结果', status_code=403)
    with SessionLocal() as session:
        names = select_current(DepartmentWorkOrderMovement.worker_name).where(DepartmentWorkOrderMovement.document_type == 'piecework')
        if worker_name:
            names = names.where(DepartmentWorkOrderMovement.worker_name.ilike(f'%{worker_name.strip()}%'))
        names = names.distinct().subquery()
        total = session.scalar(select_current(func.count()).select_from(names)) or 0
        workers = list(session.scalars(select_current(names.c.worker_name).order_by(names.c.worker_name).offset((page - 1) * page_size).limit(page_size)))
        if not workers:
            return [], total
        issues = session.execute(select_current(DepartmentWorkOrderMovement, DepartmentHandoffTicket.id)
            .join(DepartmentHandoffTicket, DepartmentHandoffTicket.issue_movement_id == DepartmentWorkOrderMovement.id)
            .where(DepartmentWorkOrderMovement.document_type == 'piecework', DepartmentWorkOrderMovement.worker_name.in_(workers))
            .order_by(DepartmentWorkOrderMovement.id.desc())).all()
        roots = list(session.scalars(select_current(QcInspection.id).where(QcInspection.source_ticket_id.in_({ticket for _, ticket in issues}))))
        history, reworks = batch_history(session, roots) if roots else ([], [])
        labels = order_labels(session, {issue.work_order_id for issue, _ in issues} | {record.work_order_id for _, _, record in history})
        users = usernames_by_ids(session, {record.actor_user_id for _, _, record in history} | {event.actor_user_id for _, event in reworks if event is not None})
        batches = build_batches(roots, history, reworks, labels, users, department_names(session))
        by_ticket = {batch['source_ref']: batch for batch in batches}
        groups = {name: {'worker_name': name, 'tickets': []} for name in workers}
        for issue, ticket in issues:
            groups[issue.worker_name]['tickets'].append(ticket_result(issue, ticket, by_ticket.get(f'JT-{ticket:08d}'), labels[issue.work_order_id]))
        for group in groups.values():
            for key in ['quantity', 'good_quantity', 'scrap_quantity', 'unsettled_quantity']:
                group[key] = str(sum(int(ticket[key]) for ticket in group['tickets']))
        return list(groups.values()), total
