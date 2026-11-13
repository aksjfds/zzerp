from sqlalchemy import select

from modules.engineering.route_api import current_route_references
from modules.errors import DomainError
from modules.planning.persistence import DepartmentWorkOrder


def load_scoped_order(session, order_id: int, department_scope: str | None):
    order = session.scalar(select(DepartmentWorkOrder).where(DepartmentWorkOrder.id == order_id)
                           .execution_options(populate_existing=True))
    if order is None:
        raise DomainError("department_work_order_not_found", "部门工单不存在", status_code=404)
    route = current_route_references(session, route_keys={
        (order.product_id, order.material_node_id, order.department_node_id),
    }).get((order.product_id, order.material_node_id, order.department_node_id))
    if route is None:
        raise DomainError("department_work_order_route_missing", "工单的当前路线不存在", status_code=409)
    if department_scope is not None and route.department_code != department_scope:
        raise DomainError("department_access_denied", "只能操作和查看本部门工单", status_code=403)
    return order
