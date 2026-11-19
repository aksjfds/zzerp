"""Read-only batch lineage and causally ordered inspection/rework events."""

from domain.time import BUSINESS_TIMEZONE
from sqlalchemy import func, literal, select
from sqlalchemy.orm import aliased

from modules.planning.persistence import QcInspection, QcReworkEvent, QcReworkTicket


def batch_page(session, page, page_size):
    roots = select(QcInspection.id).where(QcInspection.source_return_id.is_(None))
    total = session.scalar(select(func.count()).select_from(roots.subquery())) or 0
    ids = list(session.scalars(roots.order_by(QcInspection.id.desc()).offset((page - 1) * page_size).limit(page_size)))
    return ids, total


def batch_history(session, root_ids):
    lineage = select(QcInspection.id.label('root_id'), QcInspection.id.label('inspection_id'),
        literal(0).label('round')).where(QcInspection.id.in_(root_ids)).cte('qc_lineage', recursive=True)
    child = aliased(QcInspection)
    descendants = select(lineage.c.root_id, child.id, (lineage.c.round + 1).label('round')).select_from(lineage)\
        .join(QcReworkTicket, QcReworkTicket.inspection_id == lineage.c.inspection_id)\
        .join(QcReworkEvent, (QcReworkEvent.ticket_id == QcReworkTicket.id) & (QcReworkEvent.action == 'return'))\
        .join(child, child.source_return_id == QcReworkEvent.id)
    lineage = lineage.union_all(descendants)
    records = session.execute(select(lineage.c.root_id, lineage.c.round, QcInspection).select_from(lineage)
        .join(QcInspection, QcInspection.id == lineage.c.inspection_id)
        .order_by(lineage.c.root_id, lineage.c.round, QcInspection.id)).all()
    reworks = session.execute(select(QcReworkTicket, QcReworkEvent).outerjoin(
        QcReworkEvent, QcReworkEvent.ticket_id == QcReworkTicket.id)
        .where(QcReworkTicket.inspection_id.in_({record.id for _, _, record in records}))).all()
    return records, reworks


def event_time(value):
    return value.astimezone(BUSINESS_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')


def inspection_row(record, labels, users, departments):
    if record.source_ticket_id is not None:
        source = f'JT-{record.source_ticket_id:08d}'
    elif record.source_pick_id is not None:
        source = f'WL-{record.source_pick_id:08d}'
    else:
        source = f'FH-{record.source_return_id:08d}'
    return dict(id=record.id, source_ref=source, **labels[record.work_order_id],
        quantity=str(record.good_quantity + record.scrap_quantity + record.rework_quantity),
        good_quantity=str(record.good_quantity), scrap_quantity=str(record.scrap_quantity),
        rework_quantity=str(record.rework_quantity),
        repair_department=departments[record.repair_department_code] if record.repair_department_code else '',
        actor_username=users[record.actor_user_id], created_at=event_time(record.created_at), note=record.note)


def inspection_event(record, round_number, ticket_id, labels, users, departments):
    row = inspection_row(record, labels, users, departments)
    return {'key': f'inspection:{record.id}', 'kind': 'inspection', 'round': round_number,
        'created_at': row['created_at'], 'actor_username': row['actor_username'], 'note': row['note'],
        'quantity': row['quantity'], 'department': row['department'],
        'ticket_no': f'FX-{ticket_id:08d}' if ticket_id is not None else '', 'inspection': row,
        'repaired_quantity': '0', 'unrepaired_quantity': '0'}


def repair_event(event, round_number, department, users):
    return {'key': f'rework:{event.id}', 'kind': event.action, 'round': round_number + 1,
        'created_at': event_time(event.created_at), 'actor_username': users[event.actor_user_id],
        'note': event.note, 'quantity': str(event.quantity), 'department': department,
        'ticket_no': f'FX-{event.ticket_id:08d}' if event.action == 'receive' else f'FH-{event.id:08d}',
        'repaired_quantity': str(event.repaired_quantity), 'unrepaired_quantity': str(event.unrepaired_quantity),
        'inspection': None}


def batch_status(record, events):
    if not record.rework_quantity:
        return 'finished'
    actions = {event.action for event in events}
    if 'return' in actions:
        return 'awaiting_reinspection'
    return 'repairing' if 'receive' in actions else 'awaiting_repair_receipt'


def build_batches(root_ids, records, reworks, labels, users, departments):
    tickets, repair_events = {}, {}
    for ticket, event in reworks:
        tickets[ticket.inspection_id] = ticket.id
        if event is not None:
            repair_events.setdefault(ticket.inspection_id, []).append(event)
    batches = {}
    for root_id, round_number, record in records:
        event = inspection_event(record, round_number, tickets.get(record.id), labels, users, departments)
        if root_id not in batches:
            row = event['inspection']
            batches[root_id] = {'id': root_id, 'source_ref': row['source_ref'],
                'order_no': row['order_no'], 'product': row['product'], 'material': row['material'],
                'quantity': row['quantity'], 'events': []}
        batch = batches[root_id]
        batch['events'].append(event)
        repairs = sorted(repair_events.get(record.id, []), key=lambda item: (item.action != 'receive', item.created_at, item.id))
        batch['events'].extend(repair_event(item, round_number, event['inspection']['repair_department'], users) for item in repairs)
        batch['status'] = batch_status(record, repairs)
    return [batches[root_id] for root_id in root_ids]
