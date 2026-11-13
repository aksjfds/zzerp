"""Independent departmental receipts/issues and immutable movement history."""

from sqlalchemy import func, or_, select, tuple_

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE
from modules.engineering.route_api import handoff_contexts, current_route_references
from modules.engineering.product_reference_api import resolve_plan_product, get_product_references
from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.organization.read_api import allows_receipts, department_names
from modules.planning.persistence import DepartmentWorkOrder, DepartmentWorkOrderMovement, DepartmentHandoffTicket, DepartmentMovementReceiptLink, ProductionPlan
from modules.planning.work_order_access import load_scoped_order
from modules.planning.handoffs import order_context, ticket_number
from modules.planning.queries import load_plan
from modules.planning.issue_limits import available_issue_quantity
from schemas.planning import DepartmentMovementCreate


def ensure_plan_without_movements(session, plan_id: int) -> None:
    exists = session.scalar(
        select(DepartmentWorkOrderMovement.id)
        .join(DepartmentWorkOrder, DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id)
        .where(DepartmentWorkOrder.production_plan_id == plan_id).limit(1)
    )
    if exists is not None:
        raise DomainError("plan_has_material_movements", "计划已有到料或出料流水，不能撤回、重建或删除工单", status_code=409)


def movement_totals(session, order_ids: set[int]) -> dict[int, tuple[str, str]]:
    if not order_ids:
        return {}
    orders = list(session.scalars(select(DepartmentWorkOrder).where(DepartmentWorkOrder.id.in_(order_ids))))
    contexts = handoff_contexts(session, {order.product_id for order in orders})
    grouped = session.execute(select(DepartmentWorkOrderMovement.work_order_id,
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
    result = {}
    for order in orders:
        parts = receipts.get(order.id, {})
        context = contexts[order.product_id]
        if set(parts) <= {order.material_node_id}:
            received = parts.get(order.material_node_id, "0")
        else:
            received = "；".join(f"{context['materials'][key]} {value}" for key, value in sorted(parts.items()))
        result[order.id] = (received, issues.get(order.id, "0"))
    return result


def serialize_movements(session, movements) -> list[dict]:
    names = usernames_by_ids(session, {row.actor_user_id for row in movements})
    ids = {row.id for row in movements}
    tickets = list(session.scalars(select(DepartmentHandoffTicket).where(or_(
        DepartmentHandoffTicket.issue_movement_id.in_(ids),
        DepartmentHandoffTicket.id.in_({row.ticket_id for row in movements if row.ticket_id is not None})))))
    by_issue = {row.issue_movement_id: row for row in tickets}
    by_ticket = {row.id: row for row in tickets}
    links = {}
    for issue_id, receipt_id in session.execute(select(DepartmentMovementReceiptLink.issue_movement_id,
        DepartmentMovementReceiptLink.receipt_movement_id).where(DepartmentMovementReceiptLink.issue_movement_id.in_(ids))):
        links.setdefault(issue_id, []).append(receipt_id)
    orders = {row.id: row for row in session.scalars(select(DepartmentWorkOrder)
        .where(DepartmentWorkOrder.id.in_({m.work_order_id for m in movements})))}
    contexts = handoff_contexts(session, {order.product_id for order in orders.values()})
    result = []
    for row in movements:
        order = orders[row.work_order_id]
        ticket = by_issue.get(row.id) if row.direction == "issue" else by_ticket.get(row.ticket_id)
        material = row.input_material_node_id if row.direction == "receipt" else order.material_node_id
        result.append(dict(id=row.id, direction=row.direction, quantity=row.quantity,
            note=row.note, request_id=row.request_id, actor_username=names[row.actor_user_id],
            created_at=row.created_at.astimezone(BUSINESS_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
            receipt_source=row.receipt_source, ticket_id=row.ticket_id, input_material_node_id=row.input_material_node_id,
            target_work_order_id=ticket.target_work_order_id if row.direction == "issue" and ticket else None,
            receipt_movement_ids=sorted(links.get(row.id, [])), ticket_no=ticket_number(ticket.id) if ticket else None,
            material_name=contexts[order.product_id]["materials"][material]))
    return result


def validate_movement_shape(payload):
    if payload.direction == "receipt" and payload.receipt_source == "external" and not payload.note.strip():
        raise DomainError("unattributed_receipt_note_required", "无来源到料必须填写备注", path="note")
    if payload.direction == "issue":
        valid = payload.receipt_source is None and payload.ticket_id is None and payload.input_material_node_id is None
    else:
        valid = payload.target_work_order_id is None and (
            payload.receipt_source == "external" and payload.ticket_id is None and payload.input_material_node_id is not None
            or payload.receipt_source == "ticket" and payload.ticket_id is not None and payload.input_material_node_id is None)
    if not valid:
        raise DomainError("movement_source_invalid", "请选择有效交接票或填写无来源到料资料，出料不能填写到料字段")


def resolve_receipt_input(session, order, payload, context, key):
    if payload.receipt_source == "external":
        if payload.input_material_node_id not in context["receipt_materials"][order.material_node_id]:
            raise DomainError("receipt_material_invalid", "请选择此工单的实际到料物料", status_code=403)
        return payload.input_material_node_id
    ticket = session.scalar(select(DepartmentHandoffTicket).where(DepartmentHandoffTicket.id == payload.ticket_id).with_for_update())
    if ticket is None or ticket.target_work_order_id != order.id:
        raise DomainError("handoff_ticket_denied", "交接票不存在或不是发给此工单", status_code=403)
    issue = session.get(DepartmentWorkOrderMovement, ticket.issue_movement_id)
    if payload.quantity < issue.quantity and not payload.note.strip():
        raise DomainError("partial_receipt_note_required", "登记到料数量小于交接票数量，必须填写备注", path="note")
    source = session.get(DepartmentWorkOrder, issue.work_order_id)
    source_key = (source.material_node_id, source.department_node_id)
    if source.production_plan_id != order.production_plan_id or key not in context["routes"].successors.get(source_key, frozenset()):
        raise DomainError("handoff_route_invalid", "交接票来源与当前直接路线不匹配", status_code=409)
    received = session.scalar(select(func.coalesce(func.sum(DepartmentWorkOrderMovement.quantity), 0))
        .where(DepartmentWorkOrderMovement.ticket_id == ticket.id))
    if int(received) + payload.quantity > issue.quantity:
        raise DomainError("handoff_receipt_exceeds_issue", f"交接到料不能超过上游出料，本票剩余可到料 {issue.quantity - int(received)}", status_code=409)
    return source.material_node_id


def record_movement(order_id: int, payload: DepartmentMovementCreate, *, department_scope: str | None, actor_user_id: int):
    if department_scope is None:
        raise DomainError("department_operator_required", "仅所属生产部门账号可登记到料和出料", status_code=403)
    validate_movement_shape(payload)
    with SessionLocal.begin() as session:
        order = load_scoped_order(session, order_id, department_scope)
        plan = load_plan(session, order.production_plan_id, for_update=True)
        resolve_plan_product(session, plan.product_id, plan.customer_id)
        order = load_scoped_order(session, order_id, department_scope)
        previous = session.scalar(select(DepartmentWorkOrderMovement).where(
            DepartmentWorkOrderMovement.work_order_id == order.id,
            DepartmentWorkOrderMovement.request_id == payload.request_id,
        ))
        if previous is not None:
            actual = serialize_movements(session, [previous])[0]
            expected = payload.model_dump()
            if payload.receipt_source == "ticket":
                expected["input_material_node_id"] = actual["input_material_node_id"]
            if previous.actor_user_id != actor_user_id or any(actual[key] != value for key,value in expected.items()):
                raise DomainError("movement_request_conflict", "该提交标识已用于其他登记，请重新打开录入窗口", status_code=409)
            return actual
        if plan.status != "confirmed":
            raise DomainError("plan_not_open_for_movements", "仅已确认计划的工单允许登记到料和出料", status_code=409)
        context, key = order_context(session, order)
        input_material = None
        if payload.direction == "receipt":
            if not allows_receipts(department_scope):
                raise DomainError("department_receipt_disabled", "冲压部和外购部无需登记到料，请直接出料", status_code=403)
            input_material = resolve_receipt_input(session, order, payload, context, key)
        else:
            available = available_issue_quantity(session, order, context, department_scope)
            if available is not None and payload.quantity > available:
                raise DomainError("issue_exceeds_available", f"本次出料超过剩余可出数量，当前可出 {available}", status_code=409)
            destinations = context["routes"].successors[key]
            target = session.get(DepartmentWorkOrder, payload.target_work_order_id) if payload.target_work_order_id else None
            if destinations:
                if (target is None or target.production_plan_id != order.production_plan_id
                    or (target.material_node_id,target.department_node_id) not in destinations):
                    raise DomainError("handoff_target_invalid", "请选择当前路线的合法下一步工单，不能跳步或跨计划", status_code=409)
            elif payload.target_work_order_id is not None:
                raise DomainError("handoff_terminal_target", "终端出料不能指定内部工单")
        movement = DepartmentWorkOrderMovement(work_order_id=order.id, direction=payload.direction,
            quantity=payload.quantity, note=payload.note, request_id=payload.request_id, actor_user_id=actor_user_id,
            receipt_source=payload.receipt_source, ticket_id=payload.ticket_id, input_material_node_id=input_material)
        session.add(movement)
        session.flush()
        if payload.direction == "issue":
            if payload.target_work_order_id is not None:
                session.add(DepartmentHandoffTicket(issue_movement_id=movement.id, target_work_order_id=payload.target_work_order_id))
            session.flush()
        return serialize_movements(session, [movement])[0]


def list_movements(order_id: int, page: int, page_size: int, *, department_scope: str | None,
                   input_material_node_id: str | None = None):
    with SessionLocal() as session:
        order = load_scoped_order(session, order_id, department_scope)
        condition = DepartmentWorkOrderMovement.work_order_id == order_id
        if input_material_node_id is not None:
            context, _ = order_context(session, order)
            if input_material_node_id not in context["receipt_materials"][order.material_node_id]:
                raise DomainError("receipt_material_invalid", "配件不属于此工单", status_code=403)
            condition = condition & (DepartmentWorkOrderMovement.direction == "receipt") & (
                DepartmentWorkOrderMovement.input_material_node_id == input_material_node_id)
        total = session.scalar(select(func.count()).select_from(DepartmentWorkOrderMovement).where(condition)) or 0
        movements = list(session.scalars(select(DepartmentWorkOrderMovement).where(condition)
            .order_by(func.date_trunc("second", DepartmentWorkOrderMovement.created_at).asc(),
                      DepartmentWorkOrderMovement.id.asc())
            .offset((page - 1) * page_size).limit(page_size)))
        return serialize_movements(session, movements), total


def list_department_movements(page: int, page_size: int, *, department_scope: str | None, department_code: str | None = None):
    if department_scope is not None and department_code not in {None, department_scope}:
        raise DomainError("department_access_denied", "只能查看本部门流水", status_code=403)
    department_code = department_scope or department_code
    with SessionLocal() as session:
        names = department_names(session)
        if department_code is not None and department_code not in names:
            raise DomainError("department_not_found", "生产部门不存在", status_code=404)
        conditions = []
        if department_code is not None:
            keys = set(current_route_references(session, department_code=department_code))
            conditions.append(tuple_(DepartmentWorkOrder.product_id, DepartmentWorkOrder.material_node_id,
                                     DepartmentWorkOrder.department_node_id).in_(keys))
        query = (select(DepartmentWorkOrderMovement, DepartmentWorkOrder, ProductionPlan)
            .join(DepartmentWorkOrder, DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id)
            .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id).where(*conditions))
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.execute(query.order_by(func.date_trunc("second", DepartmentWorkOrderMovement.created_at).asc(),
            DepartmentWorkOrderMovement.id.asc()).offset((page-1)*page_size).limit(page_size)).all()
        data = serialize_movements(session, [movement for movement, order, plan in rows])
        products = get_product_references(session, {order.product_id for movement, order, plan in rows})
        refs = current_route_references(session, route_keys={
            (order.product_id,order.material_node_id,order.department_node_id) for movement,order,plan in rows})
        for entry, (movement, order, plan) in zip(data, rows):
            ref = refs.get((order.product_id,order.material_node_id,order.department_node_id))
            if ref is None:
                raise DomainError("department_work_order_route_missing", "流水来源工单的路线不存在", status_code=409)
            product = products[order.product_id]
            entry.update(order_no=plan.order_no, factory_code=product.factory_code,
                         product_name=product.product_name, department_name=names[ref.department_code])
        return data, total
