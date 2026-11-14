"""Movement reads and aggregation, scoped before counting and pagination."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.engineering.api import (
    appearance_names,
    current_route_references,
    get_product_references,
)
from zzerp.modules.organization.api import department_names
from zzerp.modules.planning.handoffs import order_context
from zzerp.modules.planning.movement_serializers import serialize_movements
from zzerp.modules.planning.persistence import (
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    ProductionPlan,
    movement_second,
)
from zzerp.modules.planning.work_order_access import department_order_condition, load_scoped_order


def list_movements(
    session: Session,
    order_id: int,
    page: int,
    page_size: int,
    *,
    department_scope: str | None,
    input_material_node_id: str | None = None,
):
    order = load_scoped_order(session, order_id, department_scope)
    condition = DepartmentWorkOrderMovement.work_order_id == order_id
    if input_material_node_id is not None:
        context, _ = order_context(session, order)
        if input_material_node_id not in context.receipt_materials[order.material_node_id]:
            raise DomainError("receipt_material_invalid", "配件不属于此工单", status_code=403)
        condition = (
            condition
            & (DepartmentWorkOrderMovement.direction == "receipt")
            & (DepartmentWorkOrderMovement.input_material_node_id == input_material_node_id)
        )
    total = (
        session.scalar(
            select(func.count()).select_from(DepartmentWorkOrderMovement).where(condition)
        )
        or 0
    )
    movements = list(
        session.scalars(
            select(DepartmentWorkOrderMovement)
            .where(condition)
            .order_by(
                movement_second().asc(),
                DepartmentWorkOrderMovement.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return serialize_movements(session, movements), total


def list_department_movements(
    session: Session,
    page: int,
    page_size: int,
    *,
    department_scope: str | None,
    department_code: str | None = None,
):
    if department_scope is not None and department_code not in {None, department_scope}:
        raise DomainError("department_access_denied", "只能查看本部门流水", status_code=403)
    department_code = department_scope or department_code
    names = department_names(session)
    if department_code is not None and department_code not in names:
        raise DomainError("department_not_found", "生产部门不存在", status_code=404)
    conditions = []
    if department_code is not None:
        conditions.append(department_order_condition(department_code))
    query = (
        select(DepartmentWorkOrderMovement, DepartmentWorkOrder, ProductionPlan)
        .join(
            DepartmentWorkOrder, DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id
        )
        .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
        .where(*conditions)
    )
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.execute(
        query.order_by(
            movement_second().asc(),
            DepartmentWorkOrderMovement.id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    data = serialize_movements(session, [movement for movement, order, plan in rows])
    products = get_product_references(session, {order.product_id for movement, order, plan in rows})
    appearance_labels = appearance_names(
        session, {order.appearance_id for movement, order, plan in rows}
    )
    refs = current_route_references(
        session,
        route_keys={
            (
                order.product_id,
                order.appearance_id,
                order.material_node_id,
                order.department_node_id,
            )
            for movement, order, plan in rows
        },
    )
    for entry, (movement, order, plan) in zip(data, rows):
        ref = refs.get(
            (
                order.product_id,
                order.appearance_id,
                order.material_node_id,
                order.department_node_id,
            )
        )
        if ref is None:
            raise DomainError(
                "department_work_order_route_missing", "流水来源工单的路线不存在", status_code=409
            )
        product = products[order.product_id]
        entry.update(
            appearance_id=order.appearance_id,
            appearance_name=appearance_labels[order.appearance_id],
            order_no=plan.order_no,
            factory_code=product.factory_code,
            product_name=product.product_name,
            department_name=names[ref.department_code],
        )
    return data, total
