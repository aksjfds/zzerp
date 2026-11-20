"""One scoped, paged inbox for normal, repair and QC return tickets."""

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE
from sqlalchemy import BigInteger, case, func, literal, or_, union_all
from sqlalchemy.orm import aliased

from modules.errors import DomainError
from modules.organization.read_api import RECEIPT_DISABLED_CODES, department_names
from modules.planning.current_records import select_current
from modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    OutsourceDispatch,
    OutsourceReturn,
    PlanProductRoute,
    ProductionPlan,
    QcInspection,
    QcReworkEvent,
    QcReworkTicket,
    WarehousePick,
)
from modules.planning.snapshots import (
    material_labels,
)


def route_condition(route, order):
    return ((route.production_plan_id == order.production_plan_id)
            & (route.product_id == order.product_id)
            & (route.material_node_id == order.material_node_id)
            & (route.department_node_id == order.department_node_id))


def normal_tickets():
    source, target = aliased(DepartmentWorkOrder), aliased(DepartmentWorkOrder)
    source_route, target_route = aliased(PlanProductRoute), aliased(PlanProductRoute)
    receipt = aliased(DepartmentWorkOrderMovement)
    received = select_current(receipt.id).where(receipt.ticket_id == DepartmentHandoffTicket.id).exists()
    received_quantity = select_current(func.coalesce(func.sum(receipt.quantity), 0)).where(
        receipt.ticket_id == DepartmentHandoffTicket.id).scalar_subquery()
    inspected = select_current(QcInspection.id).where(QcInspection.source_ticket_id == DepartmentHandoffTicket.id).exists()
    action = case((received & (target_route.department_code == 'outsource'), 'outsource'),
                  (received | inspected, 'none'), (target_route.department_code == 'qc', 'inspect'),
                  (target_route.department_code.in_(RECEIPT_DISABLED_CODES), 'none'), else_='receive')
    return (select_current(literal('normal').label('kind'), DepartmentHandoffTicket.id.label('id'),
        source.id.label('material_order_id'), target.id.label('target_order_id'), target.production_plan_id.label('plan_id'),
        source_route.department_code.label('source_code'), target_route.department_code.label('target_code'),
        DepartmentWorkOrderMovement.quantity.label('quantity'), DepartmentWorkOrderMovement.created_at.label('created_at'),
        DepartmentWorkOrderMovement.note.label('note'), action.label('action'),
        case((inspected, DepartmentWorkOrderMovement.quantity), else_=received_quantity).label('received_quantity'),
        DepartmentWorkOrderMovement.document_type.label('document_type'), DepartmentWorkOrderMovement.worker_name.label('worker_name'), DepartmentWorkOrderMovement.piecework_process.label('piecework_process'))
        .select_from(DepartmentHandoffTicket)
        .join(DepartmentWorkOrderMovement, DepartmentWorkOrderMovement.id == DepartmentHandoffTicket.issue_movement_id)
        .join(source, source.id == DepartmentWorkOrderMovement.work_order_id)
        .join(target, target.id == DepartmentHandoffTicket.target_work_order_id)
        .join(source_route, route_condition(source_route, source)).join(target_route, route_condition(target_route, target)))


def repair_tickets(*, outgoing=False):
    received_quantity = select_current(QcReworkEvent.quantity).where(QcReworkEvent.ticket_id == QcReworkTicket.id,
        QcReworkEvent.action == 'receive').scalar_subquery()
    received_note = select_current(QcReworkEvent.note).where(QcReworkEvent.ticket_id == QcReworkTicket.id,
        QcReworkEvent.action == 'receive').scalar_subquery()
    received = select_current(QcReworkEvent.id).where(QcReworkEvent.ticket_id == QcReworkTicket.id,
                                             QcReworkEvent.action == 'receive').exists()
    returned = select_current(QcReworkEvent.id).where(QcReworkEvent.ticket_id == QcReworkTicket.id,
                                             QcReworkEvent.action == 'return').exists()
    return (select_current(literal('rework').label('kind'), QcReworkTicket.id.label('id'),
        QcInspection.work_order_id.label('material_order_id'), literal(None, type_=BigInteger).label('target_order_id'),
        DepartmentWorkOrder.production_plan_id.label('plan_id'), literal('qc').label('source_code'),
        QcInspection.repair_department_code.label('target_code'),
        (QcInspection.rework_quantity if outgoing else func.coalesce(received_quantity, QcInspection.rework_quantity)).label('quantity'),
        QcInspection.created_at.label('created_at'),
        case((received_note != '', QcInspection.note + literal('；接收备注：') + received_note), else_=QcInspection.note).label('note'),
        case((returned, 'none'), (received, 'rework_return'), else_='rework_receive').label('action'),
        func.coalesce(received_quantity, 0).label('received_quantity'), literal('normal').label('document_type'), QcInspection.repair_worker_name.label('worker_name'), literal('').label('piecework_process'))
        .select_from(QcReworkTicket).join(QcInspection, QcInspection.id == QcReworkTicket.inspection_id)
        .join(DepartmentWorkOrder, DepartmentWorkOrder.id == QcInspection.work_order_id))


def return_tickets():
    inspected = aliased(QcInspection)
    done = select_current(inspected.id).where(inspected.source_return_id == QcReworkEvent.id).exists()
    return (select_current(literal('return').label('kind'), QcReworkEvent.id.label('id'),
        QcInspection.work_order_id.label('material_order_id'), QcInspection.work_order_id.label('target_order_id'),
        DepartmentWorkOrder.production_plan_id.label('plan_id'), QcInspection.repair_department_code.label('source_code'),
        literal('qc').label('target_code'), QcReworkEvent.quantity.label('quantity'),
        QcReworkEvent.created_at.label('created_at'), QcReworkEvent.note.label('note'),
        case((done, 'none'), else_='inspect').label('action'),
        case((done, QcReworkEvent.quantity), else_=0).label('received_quantity'), literal('normal').label('document_type'), literal('').label('worker_name'), literal('').label('piecework_process'))
        .select_from(QcReworkEvent).join(QcReworkTicket, QcReworkTicket.id == QcReworkEvent.ticket_id)
        .join(QcInspection, QcInspection.id == QcReworkTicket.inspection_id)
        .join(DepartmentWorkOrder, DepartmentWorkOrder.id == QcInspection.work_order_id)
        .where(QcReworkEvent.action == 'return'))



def warehouse_tickets():
    inspected = select_current(QcInspection.id).where(QcInspection.source_pick_id == WarehousePick.id).exists()
    receipt = aliased(DepartmentWorkOrderMovement)
    received_quantity = select_current(func.coalesce(func.sum(receipt.quantity), 0)).where(receipt.warehouse_pick_id == WarehousePick.id).scalar_subquery()
    received = select_current(receipt.id).where(receipt.warehouse_pick_id == WarehousePick.id).exists()
    action = case((received & (PlanProductRoute.department_code == 'outsource'), 'outsource'),
                  (received | inspected, 'none'), (PlanProductRoute.department_code == 'qc', 'inspect'), else_='receive')
    return (select_current(literal('warehouse').label('kind'), WarehousePick.id.label('id'),
        WarehousePick.route_warehouse_order_id.label('material_order_id'), WarehousePick.target_order_id.label('target_order_id'),
        DepartmentWorkOrder.production_plan_id.label('plan_id'), literal('warehouse').label('source_code'),
        PlanProductRoute.department_code.label('target_code'), WarehousePick.quantity.label('quantity'),
        WarehousePick.created_at.label('created_at'), WarehousePick.note.label('note'),
        action.label('action'),
        case((inspected, WarehousePick.quantity), else_=received_quantity).label('received_quantity'), literal('normal').label('document_type'), literal('').label('worker_name'), literal('').label('piecework_process'))
        .select_from(WarehousePick).join(DepartmentWorkOrder, DepartmentWorkOrder.id == WarehousePick.target_order_id)
        .join(PlanProductRoute, route_condition(PlanProductRoute, DepartmentWorkOrder)))

def list_handoff_tickets(page, page_size, *, department_scope, unreceived=False, order_no=None, target_order_id=None, department_code=None, direction='incoming'):
    if department_scope is not None and department_code not in {None, department_scope}:
        raise DomainError('handoff_department_denied', '只能查看本部门的交接票', status_code=403)
    scope = department_scope or department_code
    tickets = union_all(normal_tickets(), repair_tickets(outgoing=direction == 'outgoing'), return_tickets(), warehouse_tickets()).subquery()
    statement = select_current(tickets, ProductionPlan.order_no, ProductionPlan.status).join(
        ProductionPlan, ProductionPlan.id == tickets.c.plan_id)
    if scope is not None:
        department = tickets.c.source_code if direction == 'outgoing' else tickets.c.target_code
        statement = statement.where(department.in_({'warehouse', 'purchase'}) if scope == 'warehouse' else department == scope)
    if order_no:
        statement = statement.where(ProductionPlan.order_no.ilike(f'%{order_no.strip()}%'))
    if target_order_id is not None:
        statement = statement.where(tickets.c.target_order_id == target_order_id)
    if unreceived:
        statement = statement.where(tickets.c.action != 'none')
    with SessionLocal() as session:
        total = session.scalar(select_current(func.count()).select_from(statement.subquery())) or 0
        rows = session.execute(statement.order_by(tickets.c.created_at.desc(), tickets.c.kind, tickets.c.id.desc())
                               .offset((page - 1) * page_size).limit(page_size)).all()
        if not rows:
            return [], total
        labels = material_labels(session, {row.material_order_id for row in rows})
        names = department_names(session)
        receipts = list(session.scalars(select_current(DepartmentWorkOrderMovement).where(
            DepartmentWorkOrderMovement.direction == 'receipt', or_(
                DepartmentWorkOrderMovement.ticket_id.in_({row.id for row in rows if row.kind == 'normal'}),
                DepartmentWorkOrderMovement.warehouse_pick_id.in_({row.id for row in rows if row.kind == 'warehouse'})))))
        receipt_ids = {('normal', row.ticket_id) if row.ticket_id is not None else ('warehouse', row.warehouse_pick_id): row.id
                       for row in receipts}
        processing = outsource_ticket_status(session, receipts)
        return [serialize_ticket(row, labels[row.material_order_id], names) | {
            'receipt_id': receipt_ids.get((row.kind, row.id)),
            'outsource_available_quantity': processing.get(receipt_ids.get((row.kind, row.id)), (None, False))[0] if row.action == 'outsource' else None,
            'outsource_pending_return': processing.get(receipt_ids.get((row.kind, row.id)), (None, False))[1] if row.action == 'outsource' else False,
        } for row in rows], total


def outsource_ticket_status(session, receipts):
    if not receipts:
        return {}
    dispatch_ids = select_current(OutsourceDispatch.id).where(OutsourceDispatch.receipt_id.in_({row.id for row in receipts}))
    returned = select_current(OutsourceReturn.dispatch_id, func.sum(OutsourceReturn.quantity).label('quantity'))\
        .where(OutsourceReturn.dispatch_id.in_(dispatch_ids)).group_by(OutsourceReturn.dispatch_id).subquery()
    batches = session.execute(select_current(OutsourceDispatch.receipt_id, OutsourceDispatch.quantity,
        func.coalesce(returned.c.quantity, 0)).outerjoin(returned, returned.c.dispatch_id == OutsourceDispatch.id)
        .where(OutsourceDispatch.receipt_id.in_({row.id for row in receipts}))).all()
    dispatched, pending = {}, set()
    for receipt_id, quantity, received in batches:
        dispatched[receipt_id] = dispatched.get(receipt_id, 0) + quantity
        if quantity > received:
            pending.add(receipt_id)
    return {row.id: (str(row.quantity - dispatched.get(row.id, 0)), row.id in pending) for row in receipts}


def serialize_ticket(row, material, names):
    prefix = {'normal': 'JT', 'rework': 'FX', 'return': 'FH', 'warehouse': 'WL'}[row.kind]
    return {'document_type': row.document_type, 'worker_name': row.worker_name, 'piecework_process': row.piecework_process, 'id': row.id, 'kind': row.kind, 'action': row.action, 'ticket_no': f'{prefix}-{row.id:08d}',
        **material, 'order_no': row.order_no, 'plan_status': row.status,
        'source_department': names[row.source_code], 'target_department': names[row.target_code],
        'can_receive': row.action == 'receive', 'quantity': row.quantity,
        'received_quantity': str(int(row.received_quantity)),
        'target_work_order_id': row.target_order_id,
        'created_at': row.created_at.astimezone(BUSINESS_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'), 'note': row.note}
