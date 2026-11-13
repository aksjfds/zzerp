"""Ticket reads and direct work-order destination choices."""

from sqlalchemy import func, select, tuple_

from database import SessionLocal
from domain.time import BUSINESS_TIMEZONE
from modules.engineering.route_api import current_route_references, handoff_contexts
from modules.engineering.product_reference_api import get_product_references
from modules.errors import DomainError
from modules.organization.read_api import department_names, allows_receipts
from modules.planning.persistence import DepartmentWorkOrder, DepartmentWorkOrderMovement, DepartmentHandoffTicket, ProductionPlan
from modules.planning.work_order_access import load_scoped_order
from modules.planning.issue_limits import available_issue_quantity


def ticket_number(ticket_id):
    return f"JT-{ticket_id:08d}"


def order_context(session, order):
    context = handoff_contexts(session, {order.product_id})[order.product_id]
    key = (order.material_node_id, order.department_node_id)
    if key not in context["routes"].successors:
        raise DomainError("handoff_route_missing", "工单与当前路线不一致", status_code=409)
    return context, key


def get_handoff_options(order_id, *, department_scope):
    with SessionLocal() as session:
        order = load_scoped_order(session, order_id, department_scope)
        context, key = order_context(session, order)
        candidates = list(session.scalars(select(DepartmentWorkOrder).where(
            DepartmentWorkOrder.production_plan_id == order.production_plan_id)))
        by_key = {(o.material_node_id, o.department_node_id): o for o in candidates}
        destination_keys = context["routes"].successors[key]
        if destination_keys - by_key.keys():
            raise DomainError("handoff_target_unarranged", "路线下一步尚未安排工单，请业务部检查计划", status_code=409)
        refs = current_route_references(session, product_ids={order.product_id})
        names = department_names(session)
        targets = []
        for target_key in sorted(destination_keys):
            target = by_key[target_key]
            ref = refs[(order.product_id, *target_key)]
            targets.append(dict(id=target.id, label=f"{names[ref.department_code]} · {ref.part_name}"))
        inputs = [dict(material_node_id=part, label=context["materials"][part])
                  for part in sorted(context["receipt_materials"][order.material_node_id])]
        department = refs[(order.product_id, *key)].department_code
        available = available_issue_quantity(session, order, context, department)
        return dict(targets=targets, external_inputs=inputs, can_receive=allows_receipts(department),
                    available_issue_quantity=str(available) if available is not None else None)


def list_handoff_tickets(page, page_size, *, department_scope, unreceived=False, order_no=None, target_order_id=None, department_code=None):
    if department_scope is not None and department_code not in {None,department_scope}:
        raise DomainError("handoff_department_denied", "只能查看发给本部门的交接票", status_code=403)
    department_code = department_scope or department_code
    with SessionLocal() as session:
        conditions = []
        refs = current_route_references(session, department_code=department_code)
        if department_code is not None:
            conditions.append(tuple_(DepartmentWorkOrder.product_id, DepartmentWorkOrder.material_node_id,
                                     DepartmentWorkOrder.department_node_id).in_(set(refs)))
        if order_no:
            conditions.append(ProductionPlan.order_no.ilike(f"%{order_no.strip()}%"))
        if target_order_id is not None:
            conditions.append(DepartmentWorkOrder.id == target_order_id)
        received = select(DepartmentWorkOrderMovement.ticket_id).where(DepartmentWorkOrderMovement.ticket_id.is_not(None))
        if unreceived:
            conditions.append(DepartmentHandoffTicket.id.not_in(received))
        query = select(DepartmentHandoffTicket, DepartmentWorkOrder, ProductionPlan).join(
            DepartmentWorkOrder, DepartmentWorkOrder.id == DepartmentHandoffTicket.target_work_order_id).join(
            ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id).where(*conditions)
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.execute(query.order_by(DepartmentHandoffTicket.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
        issues = {row.id: row for row in session.scalars(select(DepartmentWorkOrderMovement).where(
            DepartmentWorkOrderMovement.id.in_({t.issue_movement_id for t, o, p in rows})))}
        sources = {row.id: row for row in session.scalars(select(DepartmentWorkOrder).where(
            DepartmentWorkOrder.id.in_({m.work_order_id for m in issues.values()})))}
        contexts = handoff_contexts(session, {o.product_id for t, o, p in rows})
        products = get_product_references(session, set(contexts))
        page_refs = current_route_references(session, product_ids=set(contexts))
        totals = dict(session.execute(select(DepartmentWorkOrderMovement.ticket_id, func.sum(DepartmentWorkOrderMovement.quantity))
            .where(DepartmentWorkOrderMovement.ticket_id.in_({t.id for t,o,p in rows}))
            .group_by(DepartmentWorkOrderMovement.ticket_id)).all())
        names = department_names(session)
        result = []
        for ticket, order, plan in rows:
            issue = issues[ticket.issue_movement_id];source = sources[issue.work_order_id]
            source_ref = page_refs[(source.product_id,source.material_node_id,source.department_node_id)]
            target_ref = page_refs[(order.product_id,order.material_node_id,order.department_node_id)]
            result.append(dict(id=ticket.id,ticket_no=ticket_number(ticket.id),order_no=plan.order_no,
                factory_code=products[order.product_id].factory_code,product_name=products[order.product_id].product_name,
                material_name=contexts[order.product_id]["materials"][source.material_node_id],
                source_department=names[source_ref.department_code],target_department=names[target_ref.department_code],
                can_receive=allows_receipts(target_ref.department_code),
                quantity=issue.quantity,received_quantity=str(int(totals.get(ticket.id,0))),
                created_at=issue.created_at.astimezone(BUSINESS_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
                note=issue.note,target_work_order_id=order.id,plan_status=plan.status))
        return result,total
