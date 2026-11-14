"""Append-only movement commands; plan/product locks precede all validation writes."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.engineering.api import resolve_plan_product
from zzerp.modules.engineering.contracts import HandoffContext
from zzerp.modules.organization.api import allows_receipts
from zzerp.modules.planning.contracts import DepartmentMovementCreate
from zzerp.modules.planning.handoffs import order_context
from zzerp.modules.planning.issue_limits import available_issue_quantity
from zzerp.modules.planning.movement_serializers import serialize_movements
from zzerp.modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
)
from zzerp.modules.planning.queries import load_plan
from zzerp.modules.planning.work_order_access import load_scoped_order


def validate_movement_shape(payload: DepartmentMovementCreate) -> None:
    if (
        payload.direction == "receipt"
        and payload.receipt_source == "external"
        and not payload.note.strip()
    ):
        raise DomainError(
            "unattributed_receipt_note_required", "无来源到料必须填写备注", path="note"
        )
    if payload.direction == "issue":
        valid = (
            payload.receipt_source is None
            and payload.ticket_id is None
            and payload.input_material_node_id is None
        )
    else:
        valid = payload.target_work_order_id is None and (
            payload.receipt_source == "external"
            and payload.ticket_id is None
            and payload.input_material_node_id is not None
            or payload.receipt_source == "ticket"
            and payload.ticket_id is not None
            and payload.input_material_node_id is None
        )
    if not valid:
        raise DomainError(
            "movement_source_invalid", "请选择有效交接票或填写无来源到料资料，出料不能填写到料字段"
        )


def resolve_receipt_input(
    session: Session,
    order: DepartmentWorkOrder,
    payload: DepartmentMovementCreate,
    context: HandoffContext,
    key: tuple[str, str],
) -> str:
    if payload.receipt_source == "external":
        if payload.input_material_node_id not in context.receipt_materials[order.material_node_id]:
            raise DomainError(
                "receipt_material_invalid", "请选择此工单的实际到料物料", status_code=403
            )
        return payload.input_material_node_id
    ticket = session.scalar(
        select(DepartmentHandoffTicket)
        .where(DepartmentHandoffTicket.id == payload.ticket_id)
        .with_for_update()
    )
    if ticket is None or ticket.target_work_order_id != order.id:
        raise DomainError("handoff_ticket_denied", "交接票不存在或不是发给此工单", status_code=403)
    issue = session.get(DepartmentWorkOrderMovement, ticket.issue_movement_id)
    if payload.quantity < issue.quantity and not payload.note.strip():
        raise DomainError(
            "partial_receipt_note_required", "登记到料数量小于交接票数量，必须填写备注", path="note"
        )
    source = session.get(DepartmentWorkOrder, issue.work_order_id)
    source_key = (source.material_node_id, source.department_node_id)
    if (
        source.production_plan_id != order.production_plan_id
        or source.product_id != order.product_id
        or source.appearance_id != order.appearance_id
        or key not in context.routes.successors.get(source_key, frozenset())
    ):
        raise DomainError(
            "handoff_route_invalid", "交接票来源与当前直接路线不匹配", status_code=409
        )
    received = session.scalar(
        select(func.coalesce(func.sum(DepartmentWorkOrderMovement.quantity), 0)).where(
            DepartmentWorkOrderMovement.ticket_id == ticket.id
        )
    )
    if int(received) + payload.quantity > issue.quantity:
        raise DomainError(
            "handoff_receipt_exceeds_issue",
            f"交接到料不能超过上游出料，本票剩余可到料 {issue.quantity - int(received)}",
            status_code=409,
        )
    return source.material_node_id


def replay_movement(
    session: Session,
    order: DepartmentWorkOrder,
    payload: DepartmentMovementCreate,
    actor_user_id: int,
) -> dict | None:
    previous = session.scalar(
        select(DepartmentWorkOrderMovement).where(
            DepartmentWorkOrderMovement.work_order_id == order.id,
            DepartmentWorkOrderMovement.request_id == payload.request_id,
        )
    )
    if previous is None:
        return None
    actual = serialize_movements(session, [previous])[0]
    expected = payload.model_dump()
    if payload.receipt_source == "ticket":
        expected["input_material_node_id"] = actual["input_material_node_id"]
    if previous.actor_user_id != actor_user_id or any(
        actual[key] != value for key, value in expected.items()
    ):
        raise DomainError(
            "movement_request_conflict",
            "该提交标识已用于其他登记，请重新打开录入窗口",
            status_code=409,
        )
    return actual


def validate_issue(
    session: Session,
    order: DepartmentWorkOrder,
    payload: DepartmentMovementCreate,
    context: HandoffContext,
    department_code: str,
) -> int | None:
    available = available_issue_quantity(session, order, context, department_code)
    if available is not None and payload.quantity > available and not payload.note.strip():
        raise DomainError(
            "excess_issue_note_required",
            f"本次出料超过部门停留数量 {available}，必须填写备注",
            path="note",
        )
    key = (order.material_node_id, order.department_node_id)
    destinations = context.routes.successors[key]
    if not destinations:
        if payload.target_work_order_id is not None:
            raise DomainError("handoff_terminal_target", "终端出料不能指定内部工单")
        return None
    target = (
        session.get(DepartmentWorkOrder, payload.target_work_order_id)
        if payload.target_work_order_id
        else None
    )
    if (
        target is None
        or target.production_plan_id != order.production_plan_id
        or target.product_id != order.product_id
        or target.appearance_id != order.appearance_id
        or (target.material_node_id, target.department_node_id) not in destinations
    ):
        raise DomainError(
            "handoff_target_invalid",
            "请选择当前路线的合法下一步工单，不能跳步或跨计划",
            status_code=409,
        )
    return target.id


def record_movement(
    session: Session,
    order_id: int,
    payload: DepartmentMovementCreate,
    *,
    department_scope: str | None,
    actor_user_id: int,
) -> dict:
    if department_scope is None:
        raise DomainError(
            "department_operator_required",
            "仅所属生产部门账号可登记到料和出料",
            status_code=403,
        )
    validate_movement_shape(payload)
    order = load_scoped_order(session, order_id, department_scope)
    plan = load_plan(session, order.production_plan_id, for_update=True)
    resolve_plan_product(session, order.product_id, plan.customer_id)
    order = load_scoped_order(session, order_id, department_scope)
    previous = replay_movement(session, order, payload, actor_user_id)
    if previous is not None:
        return previous
    if plan.status != "confirmed":
        raise DomainError(
            "plan_not_open_for_movements",
            "仅已确认计划的工单允许登记到料和出料",
            status_code=409,
        )
    context, key = order_context(session, order)
    input_material = None
    target_id = None
    if payload.direction == "receipt":
        if not allows_receipts(department_scope):
            raise DomainError(
                "department_receipt_disabled",
                "冲压部和外购部无需登记到料，请直接出料",
                status_code=403,
            )
        input_material = resolve_receipt_input(session, order, payload, context, key)
    else:
        target_id = validate_issue(session, order, payload, context, department_scope)
    movement = DepartmentWorkOrderMovement(
        work_order_id=order.id,
        direction=payload.direction,
        quantity=payload.quantity,
        note=payload.note,
        request_id=payload.request_id,
        actor_user_id=actor_user_id,
        receipt_source=payload.receipt_source,
        ticket_id=payload.ticket_id,
        input_material_node_id=input_material,
    )
    session.add(movement)
    session.flush()
    if target_id is not None:
        session.add(
            DepartmentHandoffTicket(
                issue_movement_id=movement.id,
                target_work_order_id=target_id,
            )
        )
        session.flush()
    return serialize_movements(session, [movement])[0]
