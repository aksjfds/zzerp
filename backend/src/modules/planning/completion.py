"""Product-equivalent quantities received by finished-goods work orders."""

from sqlalchemy import func

from modules.planning.current_records import select_current
from modules.planning.issue_limits import received_kit_quantity
from modules.planning.persistence import DepartmentWorkOrderMovement
from modules.planning.snapshots import snapshot_context, snapshot_items


def completed_quantities(session, orders):
    finished = {order['id']: order for order in orders if order['department_code'] == 'finished'}
    if not finished:
        return {}
    receipts = {}
    rows = session.execute(select_current(DepartmentWorkOrderMovement.work_order_id,
        DepartmentWorkOrderMovement.input_material_node_id, func.sum(DepartmentWorkOrderMovement.quantity))
        .where(DepartmentWorkOrderMovement.work_order_id.in_(finished), DepartmentWorkOrderMovement.direction == 'receipt')
        .group_by(DepartmentWorkOrderMovement.work_order_id, DepartmentWorkOrderMovement.input_material_node_id))
    for order_id, material, quantity in rows:
        order = finished[order_id]
        key = (order['production_plan_id'], order['product_id'])
        inputs = receipts.setdefault(key, {})
        inputs[material] = inputs.get(material, 0) + int(quantity)
    result = {}
    for key, item in snapshot_items(session, set(receipts)).items():
        context = snapshot_context(item)
        result[key] = received_kit_quantity(context['product_requirements'], context['requirements'], receipts[key])
    return result
