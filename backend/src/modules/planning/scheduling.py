"""Business-owned target dates for published department work orders."""

from database import SessionLocal
from schemas.planning import WorkOrderScheduleUpdate
from sqlalchemy import select

from modules.errors import DomainError
from modules.planning.persistence import DepartmentWorkOrder
from modules.planning.queries import load_plan
from modules.planning.snapshots import (
    item_key,
    order_department_filter,
    snapshot_department_orders,
)
from modules.planning.work_order_access import load_scoped_order


def update_work_order_schedule(order_id: int, payload: WorkOrderScheduleUpdate, *, department_scope: str | None) -> list[dict]:
    if department_scope is not None:
        raise DomainError("schedule_access_denied", "生产账号不能修改排产", status_code=403)
    with SessionLocal.begin() as session:
        plan_id = session.scalar(select(DepartmentWorkOrder.production_plan_id)
                                 .where(DepartmentWorkOrder.id == order_id))
        if plan_id is None:
            raise DomainError("department_work_order_not_found", "部门工单不存在", status_code=404)
        plan = load_plan(session, plan_id, for_update=True)
        order = load_scoped_order(session, order_id, department_scope=None)
        if session.scalar(select(DepartmentWorkOrder.id).where(
            DepartmentWorkOrder.id == order.id, order_department_filter('warehouse'))) is not None:
            raise DomainError('warehouse_not_production_order', '仓库不参与部门工单排产', status_code=409)
        if plan.status != "confirmed":
            raise DomainError("schedule_plan_not_confirmed", "仅已确认的计划可以调整排产", status_code=409)
        targets = schedule_targets(session, order, payload.scheduled_date)
        revisions = {**payload.expected_revisions, order.id: payload.expected_revision}
        if any(target.schedule_revision != revisions.get(target.id) for target in targets):
            raise DomainError("schedule_revision_conflict", "排产已被修改，请刷新后重新安排", status_code=409)
        for target in targets:
            target.scheduled_date = payload.scheduled_date
            target.schedule_revision += 1
        session.flush()
        return [{"id": target.id, "scheduled_date": target.scheduled_date,
                 "schedule_revision": target.schedule_revision} for target in targets]


def schedule_targets(session, order, scheduled_date):
    if scheduled_date is None:
        return [order]
    orders = list(session.scalars(select(DepartmentWorkOrder).where(
        DepartmentWorkOrder.production_plan_id == order.production_plan_id,
        DepartmentWorkOrder.product_id == order.product_id,
        DepartmentWorkOrder.material_node_id == order.material_node_id,
        ~order_department_filter("warehouse"))))
    ranks = snapshot_department_orders(session, {item_key(order)})[item_key(order)]
    orders.sort(key=lambda target: (ranks[target.department_node_id], target.id))
    start = next(index for index, target in enumerate(orders) if target.id == order.id)
    return orders[start:]
