"""Exact unit/kit capacity from immutable movement quantities."""

from sqlalchemy import func, select

from modules.errors import DomainError
from modules.organization.read_api import allows_receipts
from modules.planning.persistence import DepartmentWorkOrderMovement


def remaining_issue_quantity(material_id, requirements, receipts, issued):
    target = requirements[material_id]
    components = {part: 0 for part in target}
    for incoming, quantity in receipts.items():
        if incoming not in requirements or not requirements[incoming].keys() <= target.keys():
            raise DomainError("issue_input_inconsistent", "到料组成与当前工单不一致，请检查工程资料", status_code=409)
        for part, units in requirements[incoming].items():
            components[part] += quantity * units
    kits = min(components[part] // units for part, units in target.items())
    return kits - issued


def available_issue_quantity(session, order, context, department_code):
    if not allows_receipts(department_code):
        return None
    rows = session.execute(select(DepartmentWorkOrderMovement.direction,
        DepartmentWorkOrderMovement.input_material_node_id, func.sum(DepartmentWorkOrderMovement.quantity))
        .where(DepartmentWorkOrderMovement.work_order_id == order.id)
        .group_by(DepartmentWorkOrderMovement.direction, DepartmentWorkOrderMovement.input_material_node_id))
    receipts, issued = {}, 0
    for direction, material, quantity in rows:
        if direction == "receipt":
            receipts[material] = int(quantity)
        else:
            issued += int(quantity)
    return remaining_issue_quantity(order.material_node_id, context["requirements"], receipts, issued)
