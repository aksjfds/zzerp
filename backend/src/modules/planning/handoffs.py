"""Ticket reads and direct work-order destination choices."""

from database import SessionLocal
from sqlalchemy import select

from modules.errors import DomainError
from modules.organization.read_api import allows_receipts, department_names
from modules.planning.issue_limits import available_issue_quantity
from modules.planning.persistence import DepartmentWorkOrder
from modules.planning.snapshots import (
    handoff_contexts,
    item_key,
    route_references,
)
from modules.planning.work_order_access import load_scoped_order


def ticket_number(ticket_id):
    return f"JT-{ticket_id:08d}"


def order_context(session, order):
    context = handoff_contexts(session, {item_key(order)})[item_key(order)]
    key = (order.material_node_id, order.department_node_id)
    if key not in context["routes"].successors:
        raise DomainError("handoff_route_missing", "工单与计划快照路线不一致", status_code=409)
    return context, key


def get_handoff_options(order_id, *, department_scope):
    with SessionLocal() as session:
        order = load_scoped_order(session, order_id, department_scope)
        context, key = order_context(session, order)
        candidates = list(session.scalars(select(DepartmentWorkOrder).where(
            DepartmentWorkOrder.production_plan_id == order.production_plan_id,
            DepartmentWorkOrder.product_id == order.product_id)))
        by_key = {(o.material_node_id, o.department_node_id): o for o in candidates}
        destination_keys = context["routes"].successors[key]
        if destination_keys - by_key.keys():
            raise DomainError("handoff_target_unarranged", "路线下一步尚未安排工单，请业务部检查计划", status_code=409)
        refs = route_references(session, item_keys={item_key(order)})
        names = department_names(session)
        targets = []
        for target_key in sorted(destination_keys):
            target = by_key[target_key]
            ref = refs[(*item_key(order), *target_key)]
            targets.append({"id": target.id, "label": f"{names[ref.department_code]} · {ref.part_name}",
                            "department_name": names[ref.department_code]})
        department = refs[(*item_key(order), *key)].department_code
        available = available_issue_quantity(session, order, context, department)
        return {"targets": targets, "can_receive": allows_receipts(department),
                "available_issue_quantity": str(available) if available is not None else None}
