"""Atomic inspection and quantity-based rework handling."""

from database import SessionLocal
from schemas.quality import QcInspectionCreate, QcReworkAction
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from modules.errors import DomainError
from modules.organization.read_api import (
    department_names,
    operating_department,
    requires_inspection,
)
from modules.planning.current_records import require_effective, select_current
from modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    QcInspection,
    QcReworkEvent,
    QcReworkTicket,
    WarehousePick,
)
from modules.planning.quality_origin import batch_origin
from modules.planning.queries import load_plan
from modules.planning.work_order_access import load_scoped_order


def require_open_plan(session, order_id):
    plan_id = session.scalar(select_current(DepartmentWorkOrder.production_plan_id).where(DepartmentWorkOrder.id == order_id))
    if plan_id is None:
        raise DomainError('qc_order_missing', '质检工单不存在', status_code=404)
    return load_plan(session, plan_id, for_update=True)


def qc_source_origin(kind, source_id, *, department_scope):
    if not requires_inspection(department_scope):
        raise DomainError('qc_operator_required', '仅QC可查询质检来源归属', status_code=403)
    with SessionLocal() as session:
        order_id, _ = inspection_source(session, kind, source_id)
        load_scoped_order(session, order_id, department_scope)
        return batch_origin(session, kind, source_id)


def require_confirmed(plan):
    if plan.status != 'confirmed':
        raise DomainError('qc_plan_closed', '仅已确认计划允许质检和返修操作', status_code=409)


def inspection_source(session, kind, source_id):
    if kind == 'warehouse':
        pick = session.scalar(select_current(WarehousePick).where(WarehousePick.id == source_id))
        if pick is None:
            raise DomainError('qc_warehouse_pick_missing', '仓库领料单不存在', status_code=404)
        return pick.target_order_id, pick.quantity
    if kind == 'handoff':
        row = session.execute(select_current(DepartmentHandoffTicket, DepartmentWorkOrderMovement)
            .join(DepartmentWorkOrderMovement, DepartmentWorkOrderMovement.id == DepartmentHandoffTicket.issue_movement_id)
            .where(DepartmentHandoffTicket.id == source_id)).first()
        if row is None:
            raise DomainError('qc_source_missing', '来料交接票不存在', status_code=404)
        ticket, issue = row
        return ticket.target_work_order_id, issue.quantity
    row = session.execute(select_current(QcInspection.work_order_id, QcReworkEvent.quantity).select_from(QcInspection)
        .join(QcReworkTicket, QcReworkTicket.inspection_id == QcInspection.id)
        .join(QcReworkEvent, QcReworkEvent.ticket_id == QcReworkTicket.id)
        .where(QcReworkEvent.id == source_id, QcReworkEvent.action == 'return')).first()
    if row is None:
        raise DomainError('qc_return_missing', '返修回交票不存在', status_code=404)
    return row


def inspection_values(payload):
    return {'source_ticket_id': payload.source_id if payload.source_kind == 'handoff' else None,
            'source_return_id': payload.source_id if payload.source_kind == 'return' else None,
            'source_pick_id': payload.source_id if payload.source_kind == 'warehouse' else None,
            'good_quantity': payload.good_quantity, 'scrap_quantity': payload.scrap_quantity,
            'rework_quantity': payload.rework_quantity, 'repair_department_code': payload.repair_department_code,
            'repair_kind': payload.repair_kind, 'note': payload.note}


def check_inspection_source(session, order, payload, quantity):
    worker = ''
    if bool(payload.rework_quantity) != (payload.repair_kind is not None):
        raise DomainError('qc_repair_kind_required', '有返修时必须选择返修类型，无返修时不能填写')
    if payload.rework_quantity:
        origin = batch_origin(session, payload.source_kind, payload.source_id)
        worker = origin['worker_name'] if payload.repair_kind == 'original' else ''
        same = origin['department_code'] == payload.repair_department_code
        if same != (payload.repair_kind == 'original'):
            raise DomainError('qc_repair_kind_invalid', '原部门返修必须返回原部门，跨部门返修必须选择其他部门')
    if (payload.scrap_quantity or payload.rework_quantity) and not payload.note.strip():
        raise DomainError('qc_note_required', '有报废或返修时必须填写备注', path='note')
    if payload.good_quantity + payload.scrap_quantity + payload.rework_quantity != quantity:
        raise DomainError('qc_quantity_mismatch', '合格数、报废数和返修数之和必须等于来料数量')
    if bool(payload.rework_quantity) != (payload.repair_department_code is not None):
        raise DomainError('qc_repair_required', '有返修数量时必须选择返修部门，无返修时不能选择')
    if payload.rework_quantity and (requires_inspection(payload.repair_department_code)
        or payload.repair_department_code not in department_names(session, {payload.repair_department_code})):
        raise DomainError('qc_repair_target', '请选择有效的非QC返修部门', status_code=403)
    if payload.source_kind == 'handoff':
        check_handoff_source(session, order, payload.source_id)
    return worker


def check_handoff_source(session, order, ticket_id):
    ticket = session.scalar(select_current(DepartmentHandoffTicket).where(DepartmentHandoffTicket.id == ticket_id).with_for_update())
    if ticket is None:
        raise DomainError('qc_source_revoked', '来源出料已撤回，请刷新', status_code=409)
    issue = session.scalar(select_current(DepartmentWorkOrderMovement).where(DepartmentWorkOrderMovement.id == ticket.issue_movement_id))
    source = session.get(DepartmentWorkOrder, issue.work_order_id)
    if (source.production_plan_id, source.product_id, source.material_node_id) != (
        order.production_plan_id, order.product_id, order.material_node_id):
        raise DomainError('qc_material_mismatch', '来料与QC工单物料不一致', status_code=409)
    received = session.scalar(select_current(DepartmentWorkOrderMovement.id).where(DepartmentWorkOrderMovement.ticket_id == ticket_id))
    if received is not None:
        raise DomainError('qc_already_received', '此来料已按普通到料登记，不能重复质检', status_code=409)


def inspect_material(payload: QcInspectionCreate, *, department_scope, actor_user_id):
    if not requires_inspection(department_scope):
        raise DomainError('qc_operator_required', '仅QC账号可登记质检', status_code=403)
    try:
        with SessionLocal.begin() as session:
            order_id, quantity = inspection_source(session, payload.source_kind, payload.source_id)
            plan = require_open_plan(session, order_id)
            order_id, quantity = inspection_source(session, payload.source_kind, payload.source_id)
            order = load_scoped_order(session, order_id, department_scope)
            previous = session.scalar(select(QcInspection).where(QcInspection.request_id == payload.request_id))
            values = inspection_values(payload)
            if previous is not None:
                require_effective(previous)
                if previous.actor_user_id != actor_user_id or any(getattr(previous, key) != value for key, value in values.items()):
                    raise DomainError('qc_request_conflict', '此提交标识已用于其他质检', status_code=409)
                return {'id': previous.id}
            require_confirmed(plan)
            repair_worker = check_inspection_source(session, order, payload, quantity)
            record = QcInspection(work_order_id=order.id, request_id=payload.request_id,
                                  actor_user_id=actor_user_id,
                                  repair_worker_name=repair_worker, **values)
            session.add(record)
            session.flush()
            if payload.rework_quantity:
                session.add(QcReworkTicket(inspection_id=record.id))
            session.flush()
            return {'id': record.id}
    except IntegrityError as exc:
        raise DomainError('qc_duplicate', '来料已质检或提交标识重复，请刷新后重试', status_code=409) from exc


def record_rework(ticket_id: int, payload: QcReworkAction, *, department_scope, actor_user_id):
    if department_scope is None or requires_inspection(department_scope):
        raise DomainError('qc_repair_operator', '仅返修目标部门可接收及回交返修票', status_code=403)
    try:
        with SessionLocal.begin() as session:
            ticket = session.get(QcReworkTicket, ticket_id)
            if ticket is None:
                raise DomainError('qc_rework_missing', '返修交接票不存在', status_code=404)
            inspection = session.scalar(select_current(QcInspection).where(QcInspection.id == ticket.inspection_id))
            if inspection is None:
                raise DomainError('qc_inspection_revoked', '原质检已撤回，返修票已失效', status_code=409)
            plan = require_open_plan(session, inspection.work_order_id)
            inspection = session.scalar(select_current(QcInspection).where(QcInspection.id == ticket.inspection_id))
            if inspection is None:
                raise DomainError('qc_inspection_revoked', '原质检已撤回，返修票已失效', status_code=409)
            if operating_department(inspection.repair_department_code) != department_scope:
                raise DomainError("qc_repair_department_denied", "此返修票不属于本部门", status_code=403)
            values = rework_values(payload)
            previous = session.scalar(select(QcReworkEvent).where(QcReworkEvent.request_id == payload.request_id))
            if previous is not None:
                require_effective(previous)
                if previous.ticket_id != ticket_id or previous.actor_user_id != actor_user_id or any(
                    getattr(previous, key) != value for key, value in values.items()):
                    raise DomainError('qc_rework_request_conflict', '此提交标识已用于其他返修登记', status_code=409)
                return {'id': previous.id}
            require_confirmed(plan)
            ensure_rework_sequence(session, ticket_id, payload.action)
            validate_rework_quantity(session, ticket_id, inspection.rework_quantity, payload, values['quantity'])
            event = QcReworkEvent(ticket_id=ticket_id, actor_user_id=actor_user_id, request_id=payload.request_id, **values)
            session.add(event)
            session.flush()
            return {'id': event.id}
    except IntegrityError as exc:
        raise DomainError('qc_rework_duplicate', '此返修操作已登记，请刷新后重试', status_code=409) from exc


def ensure_rework_sequence(session, ticket_id, action):
    actions = set(session.scalars(select_current(QcReworkEvent.action).where(QcReworkEvent.ticket_id == ticket_id)))
    if action in actions or action == 'return' and 'receive' not in actions:
        raise DomainError('qc_rework_sequence', '请先接收返修票，且每票只能接收和回交一次', status_code=409)


def rework_values(payload):
    repaired = payload.repaired_quantity or 0
    unrepaired = payload.unrepaired_quantity or 0
    note = payload.note
    if payload.action == 'return':
        summary = f'返修情况：修好 {repaired}，未修好 {unrepaired}'
        note = f'{note}；{summary}' if note else summary
    return {'action': payload.action, 'quantity': payload.quantity if payload.action == 'receive' else repaired + unrepaired,
            'repaired_quantity': repaired, 'unrepaired_quantity': unrepaired, 'note': note}


def validate_rework_quantity(session, ticket_id, ticket_quantity, payload, quantity):
    if payload.action == 'receive':
        if quantity > ticket_quantity:
            raise DomainError('qc_rework_receive_excess', '接收数量不能超过返修票数量')
        if quantity < ticket_quantity and not payload.note:
            raise DomainError('qc_rework_receive_note', '接收数量小于返修票数量，必须填写备注', path='note')
    else:
        received = session.scalar(select_current(QcReworkEvent.quantity).where(
            QcReworkEvent.ticket_id == ticket_id, QcReworkEvent.action == 'receive'))
        if quantity != received:
            raise DomainError('qc_rework_return_quantity', '修好数与未修好数之和必须等于实际接收数量')
