"""Unified material-operation ledger including original and withdrawal evidence."""

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE
from sqlalchemy import func, literal, or_, select, union_all

from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.organization.read_api import department_names
from modules.planning.current_records import OPERATION_MODELS
from modules.planning.material_movements import serialize_movements
from modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    OutsourceDispatch,
    OutsourceReturn,
    PurchaseOrder,
    PurchaseReceipt,
    QcInspection,
    QcReworkEvent,
    QcReworkTicket,
    WarehousePick,
)
from modules.planning.quality_queries import order_labels
from modules.planning.revocations import revocation_blocker
from modules.planning.snapshots import (
    handoff_contexts,
    item_key,
    material_number,
    order_department_filter,
    route_key,
    route_references,
    snapshot_items,
)


def operation_columns(kind, model, order_id, label, quantity, input_material=None):
    return [literal(kind).label('kind'), model.id.label('id'), order_id.label('order_id'),
        label.label('label'), quantity.label('quantity'), model.actor_user_id.label('actor_id'),
        model.created_at.label('created_at'), model.note.label('note'), model.revoked_at.label('revoked_at'),
        model.revoked_by.label('revoked_by'), model.revoke_reason.label('revoke_reason'),
        (input_material if input_material is not None else literal(None)).label('input_material')]


def history_queries(scope):
    movement = select(*operation_columns('movement', DepartmentWorkOrderMovement,
        DepartmentWorkOrderMovement.work_order_id, DepartmentWorkOrderMovement.direction,
        DepartmentWorkOrderMovement.quantity, DepartmentWorkOrderMovement.input_material_node_id)).select_from(DepartmentWorkOrderMovement).join(DepartmentWorkOrder,
        DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id)
    if scope is not None:
        condition = order_department_filter(scope)
        if scope == 'warehouse':
            condition = condition | order_department_filter('purchase')
        movement = movement.where(condition)
    queries = [movement]
    if scope in {None, 'qc'}:
        queries.append(select(*operation_columns('inspection', QcInspection, QcInspection.work_order_id,
            literal('质检'), QcInspection.good_quantity + QcInspection.scrap_quantity + QcInspection.rework_quantity)))
    repair = select(*operation_columns('rework', QcReworkEvent, QcInspection.work_order_id,
        QcReworkEvent.action, QcReworkEvent.quantity)).select_from(QcReworkEvent).join(QcReworkTicket,
        QcReworkTicket.id == QcReworkEvent.ticket_id).join(QcInspection, QcInspection.id == QcReworkTicket.inspection_id)
    if scope is not None:
        repair = repair.where(QcInspection.repair_department_code.in_({'warehouse', 'purchase'})
            if scope == 'warehouse' else QcInspection.repair_department_code == scope)
    queries.append(repair)
    if scope in {None, 'warehouse'}:
        queries.append(select(*operation_columns('purchase', PurchaseOrder, PurchaseOrder.work_order_id,
            literal('采购'), PurchaseOrder.quantity)))
        queries.append(select(*operation_columns('purchase_receipt', PurchaseReceipt, PurchaseOrder.work_order_id,
            literal('采购到料'), PurchaseReceipt.quantity)).select_from(PurchaseReceipt)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseReceipt.purchase_order_id))
        queries.append(select(*operation_columns('warehouse', WarehousePick, WarehousePick.route_warehouse_order_id,
            literal('仓库出料'), WarehousePick.quantity)))
    if scope in {None, 'outsource'}:
        queries.append(select(*operation_columns('outsource', OutsourceDispatch,
            DepartmentWorkOrderMovement.work_order_id, literal('外发'), OutsourceDispatch.quantity, DepartmentWorkOrderMovement.input_material_node_id)).select_from(OutsourceDispatch)
            .join(DepartmentWorkOrderMovement, DepartmentWorkOrderMovement.id == OutsourceDispatch.receipt_id))
        queries.append(select(*operation_columns('outsource_return', OutsourceReturn,
            DepartmentWorkOrderMovement.work_order_id, literal('厂商到料'), OutsourceReturn.quantity, DepartmentWorkOrderMovement.input_material_node_id)).select_from(OutsourceReturn)
            .join(OutsourceDispatch, OutsourceDispatch.id == OutsourceReturn.dispatch_id)
            .join(DepartmentWorkOrderMovement, DepartmentWorkOrderMovement.id == OutsourceDispatch.receipt_id))
    return queries


def load_records(session, model, ids):
    if not ids:
        return {}
    return {row.id: row for row in session.scalars(select(model).where(model.id.in_(ids)))}


def ledger_context(session, rows):
    records = {kind: load_records(session, model, {row.id for row in rows if row.kind == kind})
               for kind, model in OPERATION_MODELS.items()}
    movements, inspections = records['movement'], records['inspection']
    ticket_ids = ({row.ticket_id for row in movements.values() if row.ticket_id is not None}
                  | {row.source_ticket_id for row in inspections.values() if row.source_ticket_id is not None})
    tickets = list(session.scalars(select(DepartmentHandoffTicket).where(or_(
        DepartmentHandoffTicket.id.in_(ticket_ids),
        DepartmentHandoffTicket.issue_movement_id.in_({row.id for row in movements.values() if row.direction == 'issue'})))))
    issues = load_records(session, DepartmentWorkOrderMovement, {row.issue_movement_id for row in tickets})
    dispatches = dict(records['outsource'])
    dispatches.update(load_records(session, OutsourceDispatch,
        {row.dispatch_id for row in records['outsource_return'].values()} - set(dispatches)))
    order_ids = ({row.order_id for row in rows} | {row.work_order_id for row in issues.values()}
                 | {row.target_work_order_id for row in tickets}
                 | {row.target_order_id for row in records['warehouse'].values()})
    orders = load_records(session, DepartmentWorkOrder, order_ids)
    refs = route_references(session, route_keys={route_key(order) for order in orders.values()})
    names = department_names(session)
    order_departments = {order.id: names[refs[route_key(order)].department_code] for order in orders.values()}
    return_ids = {row.source_return_id for row in inspections.values() if row.source_return_id is not None}
    return_sources = dict(session.execute(select(QcReworkEvent.id, QcInspection.repair_department_code)
        .select_from(QcReworkEvent)
        .join(QcReworkTicket, QcReworkTicket.id == QcReworkEvent.ticket_id)
        .join(QcInspection, QcInspection.id == QcReworkTicket.inspection_id)
        .where(QcReworkEvent.id.in_(return_ids))).all()) if return_ids else {}
    return {'records': records, 'tickets': {row.id: row for row in tickets},
        'by_issue': {row.issue_movement_id: row for row in tickets}, 'issues': issues,
        'dispatches': dispatches, 'orders': orders, 'departments': order_departments,
        'names': names, 'return_sources': return_sources}


def ticket_sender(context, ticket_id):
    ticket = context['tickets'][ticket_id]
    return context['departments'][context['issues'][ticket.issue_movement_id].work_order_id]


def event_details(row, context):
    event = context['records'][row.kind][row.id]
    note = event.note
    counterpart = ''
    if row.kind == 'movement':
        if event.piecework_process:
            note = f'工艺：{event.piecework_process}' + (f' · {note}' if note else '')
        if event.direction == 'receipt':
            counterpart = ticket_sender(context, event.ticket_id) if event.ticket_id is not None else (
                context['names']['warehouse'] if event.warehouse_pick_id is not None else '无来源到料')
        else:
            ticket = context['by_issue'].get(event.id)
            counterpart = context['departments'][ticket.target_work_order_id] if ticket else '终端出料'
    elif row.kind == 'inspection':
        if event.source_ticket_id is not None:
            counterpart = ticket_sender(context, event.source_ticket_id)
        elif event.source_pick_id is not None:
            counterpart = context['names']['warehouse']
        else:
            counterpart = context['names'][context['return_sources'][event.source_return_id]]
        note = f'合格 {event.good_quantity} / 报废 {event.scrap_quantity} / 返修 {event.rework_quantity}' + (f' · {note}' if note else '')
    elif row.kind == 'rework':
        counterpart = context['names']['qc']
    elif row.kind == 'warehouse':
        counterpart = context['departments'][event.target_order_id]
    elif row.kind in {'purchase', 'purchase_receipt'}:
        counterpart = f'采购 #{event.purchase_order_id}' if row.kind == 'purchase_receipt' else context['names']['purchase']
    else:
        dispatch = context['dispatches'][event.dispatch_id] if row.kind == 'outsource_return' else event
        counterpart = dispatch.vendor
        process = '蚀字' if dispatch.process == 'etching' else '电镀'
        note = process + (f' · {note}' if note else '')
    return counterpart, note


def timestamp(value):
    return value.astimezone(BUSINESS_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S') if value else None


def operation_label(row, context):
    if row.kind == 'movement':
        return {'receipt': '到料', 'issue': '出料'}[row.label]
    if row.kind == 'rework':
        return {'receive': '接收返修', 'return': '回交QC'}[row.label]
    if row.kind == 'inspection' and context['records']['inspection'][row.id].source_return_id is not None:
        return '复检'
    return row.label


def list_department_movements(page, page_size, *, department_scope, department_code=None):
    if department_scope is not None and department_code not in {None, department_scope}:
        raise DomainError('department_access_denied', '只能查看本部门流水', status_code=403)
    scope = department_scope or department_code
    with SessionLocal() as session:
        if scope is not None and scope not in department_names(session):
            raise DomainError('department_not_found', '生产部门不存在', status_code=404)
        operations = union_all(*history_queries(scope)).subquery()
        total = session.scalar(select(func.count()).select_from(operations)) or 0
        rows = session.execute(select(operations).order_by(func.date_trunc('second', operations.c.created_at),
            operations.c.id, operations.c.kind).offset((page-1)*page_size).limit(page_size)).all()
        if not rows:
            return [], total
        context = ledger_context(session, rows)
        orders = context['orders']
        labels = order_labels(session, {row.order_id for row in rows})
        contexts = handoff_contexts(session, {item_key(orders[row.order_id]) for row in rows})
        items = snapshot_items(session, {item_key(orders[row.order_id]) for row in rows})
        users = usernames_by_ids(session, {row.actor_id for row in rows} | {row.revoked_by for row in rows if row.revoked_by})
        printable = [record for record in context['records']['movement'].values() if record.revoked_at is None]
        prints = {record['id']: record for record in serialize_movements(session, printable)}
        result = []
        for row in rows:
            label, order = labels[row.order_id], orders[row.order_id]
            material = label['material']
            if row.input_material is not None:
                route = contexts[item_key(order)]
                material = f"{material_number(route, row.input_material)} · {route['materials'][row.input_material]}"
            counterpart, note = event_details(row, context)
            blocker = revocation_blocker(session, row.kind, context['records'][row.kind][row.id], order,
                department_scope=department_scope, plan_status=label['plan_status'])
            movement = None
            if row.kind == 'movement' and row.id in prints:
                item = items[item_key(order)]
                movement = prints[row.id] | {'kind': 'movement', 'order_no': label['order_no'],
                    'factory_code': item.factory_code, 'product_name': item.product_name,
                    'department_name': context['departments'][row.order_id]}
            result.append({'kind': row.kind, 'id': row.id, 'label': operation_label(row, context),
                'order_no': label['order_no'], 'product': label['product'], 'material': material,
                'quantity': str(row.quantity), 'created_at': timestamp(row.created_at),
                'actor_username': users[row.actor_id], 'note': note, 'counterpart': counterpart,
                'revoked_at': timestamp(row.revoked_at), 'revoked_by': users.get(row.revoked_by),
                'revoke_reason': row.revoke_reason, 'movement': movement,
                'can_revoke': blocker is None, 'revoke_blocker': blocker})
        return result, total
