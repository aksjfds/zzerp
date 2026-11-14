from sqlalchemy import ColumnElement, select, tuple_

from zzerp.errors import DomainError
from zzerp.modules.engineering.api import department_route_keys_query, route_department_code
from zzerp.modules.planning.persistence import DepartmentWorkOrder


def department_order_condition(department_code: str) -> ColumnElement[bool]:
    return tuple_(
        DepartmentWorkOrder.product_id,
        DepartmentWorkOrder.appearance_id,
        DepartmentWorkOrder.material_node_id,
        DepartmentWorkOrder.department_node_id,
    ).in_(department_route_keys_query(department_code))


def load_scoped_order(session, order_id: int, department_scope: str | None):
    order = session.scalar(
        select(DepartmentWorkOrder)
        .where(DepartmentWorkOrder.id == order_id)
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise DomainError("department_work_order_not_found", "部门工单不存在", status_code=404)
    department = route_department_code(
        session,
        order.product_id,
        order.appearance_id,
        order.material_node_id,
        order.department_node_id,
    )
    if department is None:
        raise DomainError(
            "department_work_order_route_missing", "工单的当前路线不存在", status_code=409
        )
    if department_scope is not None and department != department_scope:
        raise DomainError("department_access_denied", "只能操作和查看本部门工单", status_code=403)
    return order
