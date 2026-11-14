"""Presentation of immutable movements and their existing history links."""

from sqlalchemy import or_, select

from zzerp.errors import DomainError
from zzerp.modules.engineering.api import current_route_references, handoff_contexts
from zzerp.modules.identity.api import usernames_by_ids
from zzerp.modules.organization.api import department_names
from zzerp.modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentMovementReceiptLink,
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
)
from zzerp.time import BUSINESS_TIMEZONE


def ticket_number(ticket_id: int) -> str:
    return f"JT-{ticket_id:08d}"


def serialize_movements(session, movements) -> list[dict]:
    if not movements:
        return []
    names = usernames_by_ids(session, {row.actor_user_id for row in movements})
    ids = {row.id for row in movements}
    tickets = list(
        session.scalars(
            select(DepartmentHandoffTicket).where(
                or_(
                    DepartmentHandoffTicket.issue_movement_id.in_(ids),
                    DepartmentHandoffTicket.id.in_(
                        {row.ticket_id for row in movements if row.ticket_id is not None}
                    ),
                )
            )
        )
    )
    by_issue = {row.issue_movement_id: row for row in tickets}
    by_ticket = {row.id: row for row in tickets}
    links = {}
    for issue_id, receipt_id in session.execute(
        select(
            DepartmentMovementReceiptLink.issue_movement_id,
            DepartmentMovementReceiptLink.receipt_movement_id,
        ).where(DepartmentMovementReceiptLink.issue_movement_id.in_(ids))
    ):
        links.setdefault(issue_id, []).append(receipt_id)
    issues = {row.id: row for row in movements if row.direction == "issue"}
    missing_issues = {ticket.issue_movement_id for ticket in tickets} - issues.keys()
    if missing_issues:
        issues.update(
            {
                row.id: row
                for row in session.scalars(
                    select(DepartmentWorkOrderMovement).where(
                        DepartmentWorkOrderMovement.id.in_(missing_issues)
                    )
                )
            }
        )
    order_ids = (
        {m.work_order_id for m in movements}
        | {m.work_order_id for m in issues.values()}
        | {ticket.target_work_order_id for ticket in tickets}
    )
    orders = {
        row.id: row
        for row in session.scalars(
            select(DepartmentWorkOrder).where(DepartmentWorkOrder.id.in_(order_ids))
        )
    }
    references = current_route_references(
        session,
        route_keys={
            (
                order.product_id,
                order.appearance_id,
                order.material_node_id,
                order.department_node_id,
            )
            for order in orders.values()
        },
    )
    departments = department_names(session)
    order_departments = {}
    for order in orders.values():
        reference = references.get(
            (
                order.product_id,
                order.appearance_id,
                order.material_node_id,
                order.department_node_id,
            )
        )
        if reference is None:
            raise DomainError(
                "department_work_order_route_missing",
                "流水关联工单的当前路线不存在",
                status_code=409,
            )
        order_departments[order.id] = departments[reference.department_code]
    contexts = handoff_contexts(session, {order.appearance_id for order in orders.values()})
    result = []
    for row in movements:
        order = orders[row.work_order_id]
        ticket = by_issue.get(row.id) if row.direction == "issue" else by_ticket.get(row.ticket_id)
        material = (
            row.input_material_node_id if row.direction == "receipt" else order.material_node_id
        )
        source_id = issues[ticket.issue_movement_id].work_order_id if ticket else None
        target_id = ticket.target_work_order_id if ticket else None
        if row.direction == "receipt":
            target_id = order.id
        else:
            source_id = order.id
        result.append(
            dict(
                id=row.id,
                direction=row.direction,
                quantity=row.quantity,
                note=row.note,
                request_id=row.request_id,
                actor_username=names[row.actor_user_id],
                created_at=row.created_at.astimezone(BUSINESS_TIMEZONE).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                receipt_source=row.receipt_source,
                ticket_id=row.ticket_id,
                input_material_node_id=row.input_material_node_id,
                target_work_order_id=ticket.target_work_order_id
                if row.direction == "issue" and ticket
                else None,
                receipt_movement_ids=sorted(links.get(row.id, [])),
                ticket_no=ticket_number(ticket.id) if ticket else None,
                material_name=contexts[order.appearance_id].material_names[material],
                source_department=order_departments[source_id] if source_id is not None else None,
                target_department=order_departments[target_id] if target_id is not None else None,
            )
        )
    return result
