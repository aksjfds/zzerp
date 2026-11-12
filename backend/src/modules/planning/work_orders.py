"""Department work orders are derived assignments, without execution state."""

from sqlalchemy import delete, func, select, tuple_

from database import SessionLocal
from modules.engineering.route_api import current_route_references, validated_plan_routes
from modules.engineering.product_reference_api import get_product_references, matching_product_ids
from modules.errors import DomainError
from modules.sales.customer_api import customer_names_by_ids
from modules.organization.read_api import department_names
from modules.planning.persistence import DepartmentWorkOrder, ProductionPlan
from modules.planning.material_movements import ensure_plan_without_movements, movement_totals


def rebuild_work_orders(session, plan: ProductionPlan) -> None:
    ensure_plan_without_movements(session, plan.id)
    routes = validated_plan_routes(session, plan.product_id)
    quantities = []
    for route in routes.values():
        quantity = plan.production_quantity * route.unit_requirement
        if not 0 < quantity <= 2147483647:
            raise DomainError("department_task_quantity_invalid", "部门任务数量超出允许范围")
        quantities.append((route.material_node_id, route.department_node_id, quantity))
    session.execute(delete(DepartmentWorkOrder).where(DepartmentWorkOrder.production_plan_id == plan.id))
    session.flush()
    for material_id, department_id, quantity in quantities:
        session.add(DepartmentWorkOrder(
            production_plan_id=plan.id, product_id=plan.product_id,
            material_node_id=material_id, department_node_id=department_id, task_quantity=quantity,
        ))
    session.flush()


def list_work_orders(
    page: int, page_size: int, *, department_scope: str | None, department_code: str | None = None,
    plan_id: int | None = None, order_no: str | None = None,
    product_keyword: str | None = None,
) -> tuple[list[dict], int]:
    if department_scope is not None:
        if department_code is not None and department_code != department_scope:
            raise DomainError("department_access_denied", "只能查看本部门工单", status_code=403)
        department_code = department_scope
    with SessionLocal() as session:
        departments = department_names(session)
        if department_code is not None and department_code not in departments:
            raise DomainError("department_not_found", "生产部门不存在", status_code=404)
        conditions = []
        if department_code is not None:
            route_keys = set(current_route_references(session, department_code=department_code))
            conditions.append(tuple_(DepartmentWorkOrder.product_id, DepartmentWorkOrder.material_node_id,
                                     DepartmentWorkOrder.department_node_id).in_(route_keys))
        if plan_id is not None:
            conditions.append(ProductionPlan.id == plan_id)
        if order_no:
            conditions.append(ProductionPlan.order_no.ilike(f"%{order_no.strip()}%"))
        if product_keyword:
            conditions.append(ProductionPlan.product_id.in_(matching_product_ids(session, product_keyword)))
        statement = (
            select(DepartmentWorkOrder, ProductionPlan)
            .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
            .where(*conditions)
        )
        total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = session.execute(
            statement.order_by(DepartmentWorkOrder.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        routes = current_route_references(session, route_keys={
            (order.product_id, order.material_node_id, order.department_node_id) for order, plan in rows
        })
        products = get_product_references(session, {plan.product_id for order, plan in rows})
        customers = customer_names_by_ids(session, {plan.customer_id for order, plan in rows})
        data = []
        totals = movement_totals(session, {order.id for order, plan in rows})
        for order, plan in rows:
            route = routes.get((order.product_id, order.material_node_id, order.department_node_id))
            if route is None:
                raise DomainError("department_work_order_route_missing", "部门工单关联的当前正式路线不存在，请检查工程资料", status_code=409)
            product = products[plan.product_id]
            data.append({
                "id": order.id, "production_plan_id": plan.id, "material_node_id": order.material_node_id, "department_node_id": order.department_node_id,
                "order_no": plan.order_no, "customer_name": customers[plan.customer_id],
                "order_quantity": plan.order_quantity,
                "product_id": plan.product_id, "factory_code": product.factory_code,
                "product_name": product.product_name, "part_no": route.part_no,
                "part_name": route.part_name, "department_code": route.department_code,
                "department_name": departments[route.department_code],
                "task_quantity": order.task_quantity, "plan_status": plan.status,
                "received_quantity": totals.get(order.id, ("0", "0"))[0],
                "issued_quantity": totals.get(order.id, ("0", "0"))[1],
            })
        return data, total
