"""Independent departmental receipts/issues and immutable movement history."""

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE
from schemas.planning import DepartmentMovementCreate
from sqlalchemy import func, or_, select

from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.organization.read_api import (
    allows_manual_issue,
    allows_receipts,
    department_names,
    is_warehouse,
    requires_inspection,
)
from modules.planning.current_records import require_effective, select_current
from modules.planning.handoffs import order_context, ticket_number
from modules.planning.issue_limits import available_issue_quantity
from modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentMovementReceiptLink,
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    PurchaseOrder,
    QcInspection,
    WarehousePick,
)
from modules.planning.purchase_totals import purchase_received_totals
from modules.planning.queries import load_plan
from modules.planning.snapshots import (
    handoff_contexts,
    item_key,
    material_number,
    route_key,
    route_references,
)
from modules.planning.warehouse_stock import create_warehouse_lot
from modules.planning.work_order_access import load_material_order, load_scoped_order


def ensure_plan_without_movements(session, plan_id: int) -> None:
    exists = session.scalar(
        select(DepartmentWorkOrderMovement.id)
        .join(DepartmentWorkOrder, DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id)
        .where(DepartmentWorkOrder.production_plan_id == plan_id).limit(1)
    )
    inspected = session.scalar(select(QcInspection.id).join(
        DepartmentWorkOrder, DepartmentWorkOrder.id == QcInspection.work_order_id)
        .where(DepartmentWorkOrder.production_plan_id == plan_id).limit(1))
    picked = session.scalar(select(WarehousePick.id).join(
        DepartmentWorkOrder, DepartmentWorkOrder.id == WarehousePick.target_order_id)
        .where(DepartmentWorkOrder.production_plan_id == plan_id).limit(1))
    purchased = session.scalar(select(PurchaseOrder.id).join(DepartmentWorkOrder,
        DepartmentWorkOrder.id == PurchaseOrder.work_order_id).where(DepartmentWorkOrder.production_plan_id == plan_id).limit(1))
    if exists is not None or inspected is not None or picked is not None or purchased is not None:
        raise DomainError("plan_has_material_movements", "计划已有采购、到料、出料、质检或领料记录，不能撤回、重建或删除工单", status_code=409)


def movement_totals(session, orders, contexts) -> dict[int, tuple[str, str]]:
    if not orders:
        return {}
    order_ids = {order.id for order in orders}
    grouped = session.execute(select_current(DepartmentWorkOrderMovement.work_order_id,
        DepartmentWorkOrderMovement.direction, DepartmentWorkOrderMovement.input_material_node_id,
        func.sum(DepartmentWorkOrderMovement.quantity)).where(DepartmentWorkOrderMovement.work_order_id.in_(order_ids))
        .group_by(DepartmentWorkOrderMovement.work_order_id, DepartmentWorkOrderMovement.direction,
                  DepartmentWorkOrderMovement.input_material_node_id))
    receipts, issues = {}, {}
    for order_id, direction, material, quantity in grouped:
        if direction == "issue":
            issues[order_id] = str(int(quantity))
        else:
            receipts.setdefault(order_id, {})[material] = str(int(quantity))
    purchased = purchase_received_totals(session, order_ids)
    for order in orders:
        if order.id in purchased:
            parts = receipts.setdefault(order.id, {})
            parts[order.material_node_id] = str(int(parts.get(order.material_node_id, '0')) + purchased[order.id])
    result = {}
    for order in orders:
        parts = receipts.get(order.id, {})
        context = contexts[item_key(order)]
        if set(parts) <= {order.material_node_id}:
            received = parts.get(order.material_node_id, "0")
        else:
            received = "；".join(f"{context['materials'][key]} {value}" for key, value in sorted(parts.items()))
        result[order.id] = (received, issues.get(order.id, "0"))
    return result


def serialize_movements(session, movements) -> list[dict]:
    if not movements:
        return []
    names = usernames_by_ids(session, {row.actor_user_id for row in movements})
    ids = {row.id for row in movements}
    tickets = list(session.scalars(select_current(DepartmentHandoffTicket).where(or_(
        DepartmentHandoffTicket.issue_movement_id.in_(ids),
        DepartmentHandoffTicket.id.in_({row.ticket_id for row in movements if row.ticket_id is not None})))))
    by_issue = {row.issue_movement_id: row for row in tickets}
    by_ticket = {row.id: row for row in tickets}
    links = {}
    for issue_id, receipt_id in session.execute(select_current(DepartmentMovementReceiptLink.issue_movement_id,
        DepartmentMovementReceiptLink.receipt_movement_id).where(DepartmentMovementReceiptLink.issue_movement_id.in_(ids))):
        links.setdefault(issue_id, []).append(receipt_id)
    issues = {row.id: row for row in movements if row.direction == "issue"}
    missing_issues = {ticket.issue_movement_id for ticket in tickets} - issues.keys()
    if missing_issues:
        issues.update({row.id: row for row in session.scalars(select_current(DepartmentWorkOrderMovement)
            .where(DepartmentWorkOrderMovement.id.in_(missing_issues)))})
    pick_ids = {row.warehouse_pick_id for row in movements if row.warehouse_pick_id is not None}
    picks = {pick.id: pick for pick in session.scalars(select_current(WarehousePick).where(
        WarehousePick.id.in_(pick_ids)))} if pick_ids else {}
    order_ids = ({pick.route_warehouse_order_id for pick in picks.values()} | {m.work_order_id for m in movements} | {m.work_order_id for m in issues.values()}
                 | {ticket.target_work_order_id for ticket in tickets})
    orders = {row.id: row for row in session.scalars(select_current(DepartmentWorkOrder)
        .where(DepartmentWorkOrder.id.in_(order_ids)))}
    references = route_references(session, route_keys={route_key(order) for order in orders.values()})
    departments = department_names(session)
    order_departments = {}
    for order in orders.values():
        reference = references.get(route_key(order))
        if reference is None:
            raise DomainError("department_work_order_route_missing", "流水关联工单的计划快照路线不存在", status_code=409)
        order_departments[order.id] = departments[reference.department_code]
    contexts = handoff_contexts(session, {item_key(order) for order in orders.values()})
    result = []
    for row in movements:
        order = orders[row.work_order_id]
        ticket = by_issue.get(row.id) if row.direction == "issue" else by_ticket.get(row.ticket_id)
        material = row.input_material_node_id if row.direction == "receipt" else order.material_node_id
        source_id = issues[ticket.issue_movement_id].work_order_id if ticket else None
        target_id = ticket.target_work_order_id if ticket else None
        if row.warehouse_pick_id is not None:
            source_id = picks[row.warehouse_pick_id].route_warehouse_order_id
        if row.direction == "receipt":
            target_id = order.id
        else:
            source_id = order.id
        result.append({
            "id": row.id, "direction": row.direction, "quantity": row.quantity,
            "note": row.note, "request_id": row.request_id, "actor_username": names[row.actor_user_id],
            "document_type": row.document_type, "worker_name": row.worker_name, 'piecework_process': row.piecework_process,
            "created_at": row.created_at.astimezone(BUSINESS_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
            "receipt_source": row.receipt_source, "ticket_id": row.ticket_id,
            "warehouse_pick_id": row.warehouse_pick_id,
            "input_material_node_id": row.input_material_node_id,
            "target_work_order_id": ticket.target_work_order_id if row.direction == "issue" and ticket else None,
            "receipt_movement_ids": sorted(links.get(row.id, [])),
            "ticket_no": ticket_number(ticket.id) if ticket else None,
            "material_no": material_number(contexts[item_key(order)], material),
            "material_name": contexts[item_key(order)]["materials"][material],
            "source_department": order_departments[source_id] if source_id is not None else None,
            "target_department": order_departments[target_id] if target_id is not None else None,
        })
    return result


def validate_movement_shape(payload):
    if payload.document_type != 'piecework' and payload.piecework_process:
        raise DomainError('piecework_process_invalid', '工艺仅适用于磨房计件单', path='piecework_process')
    if payload.document_type == 'piecework' and (payload.direction != 'issue' or not payload.worker_name.strip()):
        raise DomainError('piecework_worker_required', '计件单必须填写磨房工人姓名', path='worker_name')
    if payload.document_type == 'normal' and payload.worker_name:
        raise DomainError('normal_worker_invalid', '普通单不能填写计件工人', path='worker_name')
    if payload.direction == "issue":
        valid = (payload.receipt_source is None and payload.ticket_id is None
                 and payload.warehouse_pick_id is None and payload.input_material_node_id is None)
    else:
        valid = (payload.target_work_order_id is None and payload.input_material_node_id is None and (
            payload.receipt_source == "ticket" and payload.ticket_id is not None and payload.warehouse_pick_id is None
            or payload.receipt_source == "warehouse" and payload.warehouse_pick_id is not None and payload.ticket_id is None))
    if not valid:
        raise DomainError("movement_source_invalid", "到料必须引用有效交接票，出料不能填写到料字段")


def resolve_receipt_input(session, order, payload, context, key):
    if payload.receipt_source == 'warehouse':
        return resolve_warehouse_receipt_input(session, order, payload, context, key)
    ticket = session.scalar(select_current(DepartmentHandoffTicket).where(DepartmentHandoffTicket.id == payload.ticket_id).with_for_update())
    if ticket is None or ticket.target_work_order_id != order.id:
        raise DomainError("handoff_ticket_denied", "交接票不存在或不是发给此工单", status_code=403)
    received = session.scalar(select_current(DepartmentWorkOrderMovement.id)
        .where(DepartmentWorkOrderMovement.ticket_id == ticket.id).limit(1))
    if received is not None:
        raise DomainError("handoff_ticket_already_received", "此交接票已登记到料，不能再次登记", status_code=409)
    issue = session.scalar(select_current(DepartmentWorkOrderMovement).where(DepartmentWorkOrderMovement.id == ticket.issue_movement_id))
    if payload.quantity < issue.quantity and not payload.note.strip():
        raise DomainError("partial_receipt_note_required", "登记到料数量小于交接票数量，必须填写备注", path="note")
    source = session.get(DepartmentWorkOrder, issue.work_order_id)
    source_key = (source.material_node_id, source.department_node_id)
    if (source.production_plan_id != order.production_plan_id or source.product_id != order.product_id
        or key not in context["routes"].successors.get(source_key, frozenset())):
        raise DomainError("handoff_route_invalid", "交接票来源与当前直接路线不匹配", status_code=409)
    if payload.quantity > issue.quantity:
        raise DomainError("handoff_receipt_exceeds_issue", "交接到料不能超过上游出料数量", status_code=409)
    return source.material_node_id


def resolve_warehouse_receipt_input(session, order, payload, context, key):
    pick = session.scalar(select_current(WarehousePick).where(WarehousePick.id == payload.warehouse_pick_id).with_for_update())
    if pick is None or pick.target_order_id != order.id:
        raise DomainError('warehouse_receipt_denied', '仓库交接票不存在或不是发给此工单', status_code=403)
    received = session.scalar(select_current(DepartmentWorkOrderMovement.id).where(DepartmentWorkOrderMovement.warehouse_pick_id == pick.id))
    if received is not None:
        raise DomainError('warehouse_already_received', '此仓库交接票已登记到料，不能再次登记', status_code=409)
    if payload.quantity > pick.quantity:
        raise DomainError('warehouse_receipt_exceeded', '到料数量不能超过仓库交接票数量', path='quantity')
    if payload.quantity < pick.quantity and not payload.note.strip():
        raise DomainError('warehouse_receipt_note', '到料数量小于仓库交接票数量，必须填写备注', path='note')
    source = session.get(DepartmentWorkOrder, pick.route_warehouse_order_id)
    if ((source.production_plan_id, source.product_id) != (order.production_plan_id, order.product_id)
        or not is_warehouse(context['departments'][source.department_node_id])
        or key not in context['routes'].successors.get((source.material_node_id, source.department_node_id), frozenset())):
        raise DomainError('warehouse_receipt_route', '仓库交接票来源与此工单直接路线不匹配', status_code=409)
    return source.material_node_id


def validate_issue_destination(session, order, payload, context, key, department_scope):
    available = available_issue_quantity(session, order, context, department_scope)
    if requires_inspection(department_scope) and payload.quantity > available:
        raise DomainError("qc_good_exceeded", "合格出料不能超过尚未出料的合格数量", path="quantity")
    if department_scope == 'outsource' and payload.quantity > available:
        raise DomainError('outsource_return_required',
            f'请先登记厂商回料，本次出料不能超过已回料可用数量 {max(available, 0)}', path='quantity')
    if available is not None and payload.quantity > available:
        raise DomainError("issue_quantity_exceeded",
            f"本次出料不能超过可出料数量 {max(available, 0)}", path="quantity")
    destinations = context["routes"].successors[key]
    target = session.get(DepartmentWorkOrder, payload.target_work_order_id) if payload.target_work_order_id else None
    if destinations:
        if (target is None or target.production_plan_id != order.production_plan_id
            or target.product_id != order.product_id
            or (target.material_node_id,target.department_node_id) not in destinations):
            raise DomainError("handoff_target_invalid", "请选择当前路线的合法下一步工单，不能跳步或跨计划", status_code=409)
    elif payload.target_work_order_id is not None:
        raise DomainError("handoff_terminal_target", "终端出料不能指定内部工单")
    if payload.document_type == 'piecework' and (department_scope != 'grinding' or target is None
        or context['departments'][target.department_node_id] != 'qc'):
        raise DomainError('piecework_route_invalid', '仅磨房直接出料至QC允许计件单', status_code=403)


def record_movement(order_id: int, payload: DepartmentMovementCreate, *, department_scope: str | None, actor_user_id: int):
    if department_scope is None:
        raise DomainError("department_operator_required", "仅所属生产部门账号可登记到料和出料", status_code=403)
    validate_movement_shape(payload)
    load_order = load_material_order if payload.direction == 'issue' else load_scoped_order
    with SessionLocal.begin() as session:
        order = load_order(session, order_id, department_scope)
        plan = load_plan(session, order.production_plan_id, for_update=True)
        order = load_order(session, order_id, department_scope)
        context, key = order_context(session, order)
        logical_department = context['departments'][order.department_node_id]
        if logical_department == 'purchase' and department_scope != 'warehouse':
            raise DomainError('purchase_operator_denied', '外购节点由仓库负责操作', status_code=403)
        if payload.direction == 'issue' and not allows_manual_issue(logical_department):
            raise DomainError('warehouse_manual_issue_disabled', '请在仓库库存卡片使用出料操作', status_code=403)
        previous = session.scalar(select(DepartmentWorkOrderMovement).where(
            DepartmentWorkOrderMovement.work_order_id == order.id,
            DepartmentWorkOrderMovement.request_id == payload.request_id,
        ))
        if previous is not None:
            require_effective(previous)
            actual = serialize_movements(session, [previous])[0]
            expected = payload.model_dump()
            if payload.receipt_source in {"ticket", "warehouse"}:
                expected["input_material_node_id"] = actual["input_material_node_id"]
            if previous.actor_user_id != actor_user_id or any(actual[key] != value for key,value in expected.items()):
                raise DomainError("movement_request_conflict", "该提交标识已用于其他登记，请重新打开录入窗口", status_code=409)
            return actual
        if plan.status != "confirmed":
            raise DomainError("plan_not_open_for_movements", "仅已确认计划的工单允许登记到料和出料", status_code=409)
        input_material = None
        if payload.direction == "receipt":
            if requires_inspection(department_scope) or (payload.receipt_source != 'warehouse' and not allows_receipts(department_scope)):
                raise DomainError("department_receipt_disabled", "此部门不允许普通到料，QC请登记质检", status_code=403)
            input_material = resolve_receipt_input(session, order, payload, context, key)
        else:
            validate_issue_destination(session, order, payload, context, key, logical_department)
        movement = DepartmentWorkOrderMovement(work_order_id=order.id, direction=payload.direction,
            document_type=payload.document_type, worker_name=payload.worker_name, piecework_process=payload.piecework_process,
            quantity=payload.quantity, note=payload.note, request_id=payload.request_id, actor_user_id=actor_user_id,
            receipt_source=payload.receipt_source, ticket_id=payload.ticket_id,
            warehouse_pick_id=payload.warehouse_pick_id, input_material_node_id=input_material)
        session.add(movement)
        session.flush()
        if payload.direction == 'receipt' and is_warehouse(department_scope):
            create_warehouse_lot(session, order, movement, context)
        if payload.direction == "issue":
            if payload.target_work_order_id is not None:
                session.add(DepartmentHandoffTicket(issue_movement_id=movement.id, target_work_order_id=payload.target_work_order_id))
            session.flush()
        return serialize_movements(session, [movement])[0]


def list_movements(order_id: int, page: int, page_size: int, *, department_scope: str | None,
                   input_material_node_id: str | None = None):
    with SessionLocal() as session:
        order = load_material_order(session, order_id, department_scope)
        condition = DepartmentWorkOrderMovement.work_order_id == order_id
        if input_material_node_id is not None:
            context, _ = order_context(session, order)
            if input_material_node_id not in context["receipt_materials"][order.material_node_id]:
                raise DomainError("receipt_material_invalid", "配件不属于此工单", status_code=403)
            condition = condition & (DepartmentWorkOrderMovement.direction == "receipt") & (
                DepartmentWorkOrderMovement.input_material_node_id == input_material_node_id)
        total = session.scalar(select_current(func.count()).select_from(DepartmentWorkOrderMovement).where(condition)) or 0
        movements = list(session.scalars(select_current(DepartmentWorkOrderMovement).where(condition)
            .order_by(func.date_trunc("second", DepartmentWorkOrderMovement.created_at).asc(),
                      DepartmentWorkOrderMovement.id.asc())
            .offset((page - 1) * page_size).limit(page_size)))
        return serialize_movements(session, movements), total
