from sqlalchemy import select

from modules.errors import DomainError
from modules.planning.persistence import DepartmentWorkOrder, ProductionPlan
from modules.planning.snapshots import route_key, route_references


def load_scoped_order(session, order_id: int, department_scope: str | None):
    order = session.scalar(select(DepartmentWorkOrder)
                           .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
                           .where(DepartmentWorkOrder.id == order_id,
                                  ProductionPlan.status != "draft", ProductionPlan.confirmed_at.is_not(None))
                           .execution_options(populate_existing=True))
    if order is None:
        raise DomainError("department_work_order_not_found", "部门工单不存在", status_code=404)
    route = route_references(session, route_keys={route_key(order)}).get(route_key(order))
    if route is None:
        raise DomainError("department_work_order_route_missing", "工单的计划快照路线不存在", status_code=409)
    if department_scope is not None and route.department_code != department_scope:
        raise DomainError("department_access_denied", "只能操作和查看本部门工单", status_code=403)
    return order
