"""Paged QC batches, immutable results and scoped rework tickets."""

from database import SessionLocal
from sqlalchemy import select

from modules.errors import DomainError
from modules.identity.read_api import usernames_by_ids
from modules.organization.read_api import department_names, requires_inspection
from modules.planning.persistence import (
    DepartmentWorkOrder,
    ProductionPlan,
)
from modules.planning.quality_timeline import batch_history, batch_page, build_batches
from modules.planning.snapshots import (
    item_key,
    material_number,
    route_key,
    route_references,
    snapshot_context,
    snapshot_items,
)
from modules.planning.work_order_access import load_scoped_order


def order_labels(session, order_ids):
    if not order_ids:
        return {}
    rows = session.execute(select(DepartmentWorkOrder, ProductionPlan).join(
        ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
        .where(DepartmentWorkOrder.id.in_(order_ids))).all()
    items = snapshot_items(session, {item_key(order) for order, plan in rows})
    refs = route_references(session, route_keys={route_key(order) for order, plan in rows})
    names = department_names(session)
    contexts = {key: snapshot_context(item) for key, item in items.items()}
    result = {}
    for order, plan in rows:
        item = items[item_key(order)]
        ref = refs[route_key(order)]
        result[order.id] = {'work_order_id': order.id, 'order_no': plan.order_no,
            'product': f'{item.factory_code} · {item.product_name}',
            'material': f'{material_number(contexts[item_key(order)], order.material_node_id)} · {ref.part_name}',
            'department': names[ref.department_code], 'plan_status': plan.status}
    return result


def qc_history(page, page_size, *, department_scope):
    if department_scope is not None and not requires_inspection(department_scope):
        raise DomainError('qc_history_denied', '仅QC账号可查看质检记录', status_code=403)
    with SessionLocal() as session:
        root_ids, total = batch_page(session, page, page_size)
        if not root_ids:
            return [], total
        history, reworks = batch_history(session, root_ids)
        records = [record for _, _, record in history]
        labels = order_labels(session, {record.work_order_id for record in records})
        user_ids = {record.actor_user_id for record in records} | {event.actor_user_id for _, event in reworks if event is not None}
        users = usernames_by_ids(session, user_ids)
        departments = department_names(session, {record.repair_department_code for record in records if record.repair_department_code})
        return build_batches(root_ids, history, reworks, labels, users, departments), total


def qc_repair_targets(order_id, *, department_scope):
    with SessionLocal() as session:
        order = load_scoped_order(session, order_id, department_scope)
        ref = route_references(session, route_keys={route_key(order)})[route_key(order)]
        if not requires_inspection(ref.department_code):
            raise DomainError('qc_target_order_invalid', '仅QC工单可选择返修部门', status_code=403)
        return [{'code': code, 'label': name} for code, name in department_names(session).items()
                if not requires_inspection(code)]
