"""Department work orders are derived assignments, without execution state."""

from sqlalchemy import func, select, tuple_

from database import SessionLocal
from modules.engineering.route_api import current_route_references, validated_plan_routes, handoff_contexts
from modules.engineering.product_reference_api import get_product_references, matching_product_ids
from modules.errors import DomainError
from modules.sales.customer_api import customer_names_by_ids
from modules.organization.read_api import department_names, allows_receipts, uses_assembly_tree
from modules.planning.persistence import DepartmentWorkOrder, DepartmentWorkOrderMovement, ProductionPlan, ProductionPlanItem
from modules.planning.material_movements import ensure_plan_without_movements, movement_totals


def rebuild_work_orders(session, plan: ProductionPlan) -> None:
    ensure_plan_without_movements(session, plan.id)
    quantities = []
    items = list(session.scalars(select(ProductionPlanItem)
        .where(ProductionPlanItem.production_plan_id == plan.id).order_by(ProductionPlanItem.product_id)))
    if not items:
        raise DomainError("plan_products_required", "生产计划至少需要一个产品")
    for item in items:
        for route in validated_plan_routes(session, item.product_id).values():
            quantity = item.production_quantity * route.unit_requirement
            if not 0 < quantity <= 2147483647:
                raise DomainError("department_task_quantity_invalid", "部门任务数量超出允许范围")
            quantities.append((item.product_id, route.material_node_id, route.department_node_id, quantity))
    for product_id, material_id, department_id, quantity in quantities:
        session.add(DepartmentWorkOrder(
            production_plan_id=plan.id, product_id=product_id,
            material_node_id=material_id, department_node_id=department_id, task_quantity=quantity,
        ))
    session.flush()


def assembly_components(session, orders, routes, contexts):
    candidates = [order for order in orders if uses_assembly_tree(
        routes[(order.product_id, order.material_node_id, order.department_node_id)].department_code)]
    assemblies = [order for order in candidates
                  if len(contexts[order.product_id]["requirements"][order.material_node_id]) > 1]
    if not assemblies:
        return {}
    received = {(order_id, material): int(quantity) for order_id, material, quantity in session.execute(
        select(DepartmentWorkOrderMovement.work_order_id, DepartmentWorkOrderMovement.input_material_node_id,
               func.sum(DepartmentWorkOrderMovement.quantity))
        .where(DepartmentWorkOrderMovement.work_order_id.in_({order.id for order in assemblies}),
               DepartmentWorkOrderMovement.direction == "receipt")
        .group_by(DepartmentWorkOrderMovement.work_order_id, DepartmentWorkOrderMovement.input_material_node_id))}
    result = {}
    for order in assemblies:
        context = contexts[order.product_id]
        requirements = context["requirements"][order.material_node_id]
        result[order.id] = [dict(material_node_id=part, **context["parts"][part],
            required_quantity=str(order.task_quantity * requirements[part]),
            received_quantity=str(received.get((order.id, part), 0)))
            for part in sorted(requirements, key=lambda part: context["parts"][part]["part_no"])]
    return result


def list_work_orders(
    page: int, page_size: int, *, department_scope: str | None, department_code: str | None = None,
    plan_id: int | None = None, work_order_id: int | None = None, order_no: str | None = None,
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
        if work_order_id is not None:
            conditions.append(DepartmentWorkOrder.id == work_order_id)
        if department_code is not None:
            route_keys = set(current_route_references(session, department_code=department_code))
            conditions.append(tuple_(DepartmentWorkOrder.product_id, DepartmentWorkOrder.material_node_id,
                                     DepartmentWorkOrder.department_node_id).in_(route_keys))
        if plan_id is not None:
            conditions.append(ProductionPlan.id == plan_id)
        if order_no:
            conditions.append(ProductionPlan.order_no.ilike(f"%{order_no.strip()}%"))
        if product_keyword:
            conditions.append(DepartmentWorkOrder.product_id.in_(matching_product_ids(session, product_keyword)))
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
        return serialize_work_orders(session, rows, departments=departments), total


def serialize_work_orders(session, rows, *, include_components=True, departments=None):
    if not rows:
        return []
    routes = current_route_references(session, route_keys={
        (order.product_id, order.material_node_id, order.department_node_id) for order, plan in rows
    })
    products = get_product_references(session, {order.product_id for order, plan in rows})
    items = {(item.production_plan_id, item.product_id): item for item in session.scalars(
        select(ProductionPlanItem).where(tuple_(ProductionPlanItem.production_plan_id, ProductionPlanItem.product_id)
            .in_({(order.production_plan_id, order.product_id) for order, plan in rows})))}
    customers = customer_names_by_ids(session, {plan.customer_id for order, plan in rows})
    if departments is None:
        departments = department_names(session)
    if any((order.product_id, order.material_node_id, order.department_node_id) not in routes for order, plan in rows):
        raise DomainError("department_work_order_route_missing", "部门工单关联的当前正式路线不存在，请检查工程资料", status_code=409)
    orders = [order for order, plan in rows]
    contexts = handoff_contexts(session, {order.product_id for order in orders})
    components = assembly_components(session, orders, routes, contexts) if include_components else {}
    totals = movement_totals(session, orders, contexts)
    data = []
    for order, plan in rows:
        route = routes[(order.product_id, order.material_node_id, order.department_node_id)]
        product = products[order.product_id]
        item = items[(plan.id, order.product_id)]
        data.append({
            "id": order.id, "production_plan_id": plan.id, "material_node_id": order.material_node_id, "department_node_id": order.department_node_id,
            "order_no": plan.order_no, "customer_name": customers[plan.customer_id],
            "order_quantity": item.order_quantity,
            "product_id": order.product_id, "factory_code": product.factory_code,
            "product_name": product.product_name, "part_no": route.part_no,
            "part_name": route.part_name, "department_code": route.department_code,
            "department_name": departments[route.department_code],
            "can_receive": allows_receipts(route.department_code),
            "task_quantity": order.task_quantity, "plan_status": plan.status,
            "received_quantity": totals.get(order.id, ("0", "0"))[0],
            "issued_quantity": totals.get(order.id, ("0", "0"))[1],
            "components": components.get(order.id, []),
        })
    return data
