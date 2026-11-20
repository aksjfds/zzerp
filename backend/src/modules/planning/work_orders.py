"""Department work orders are derived assignments, without execution state."""

from database import SessionLocal
from sqlalchemy import delete, func

from modules.errors import DomainError
from modules.organization.read_api import (
    allows_manual_issue,
    allows_receipts,
    department_names,
    is_warehouse,
    requires_inspection,
    uses_assembly_tree,
)
from modules.planning.current_records import select_current
from modules.planning.material_movements import (
    ensure_plan_without_movements,
    movement_totals,
)
from modules.planning.persistence import (
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    ProductionPlan,
    ProductionPlanItem,
)
from modules.planning.quality_totals import inspection_totals
from modules.planning.snapshots import (
    item_key,
    material_number,
    order_department_filter,
    order_product_filter,
    route_key,
    route_references,
    snapshot_context,
    snapshot_items,
)
from modules.planning.warehouse_stock import warehouse_dispatched
from modules.sales.customer_api import customer_names_by_ids


def rebuild_work_orders(session, plan: ProductionPlan) -> None:
    ensure_plan_without_movements(session, plan.id)
    quantities = []
    items = list(session.scalars(select_current(ProductionPlanItem)
        .where(ProductionPlanItem.production_plan_id == plan.id).order_by(ProductionPlanItem.product_id)))
    if not items:
        raise DomainError("plan_products_required", "生产计划至少需要一个产品")
    routes_by_product = {}
    for route in route_references(session, item_keys={item_key(item) for item in items}).values():
        routes_by_product.setdefault(route.product_id, []).append(route)
    for item in items:
        if item.product_id not in routes_by_product:
            raise DomainError("plan_snapshot_routes_missing", "计划产品快照缺少路线，不能确认计划", status_code=409)
        for route in routes_by_product[item.product_id]:
            quantity = item.production_quantity * route.unit_requirement
            if not 0 < quantity <= 2147483647:
                raise DomainError("department_task_quantity_invalid", "部门任务数量超出允许范围")
            quantities.append((item.product_id, route.material_node_id, route.department_node_id, quantity))
    session.execute(delete(DepartmentWorkOrder).where(
        DepartmentWorkOrder.production_plan_id == plan.id))
    for product_id, material_id, department_id, quantity in quantities:
        session.add(DepartmentWorkOrder(
            production_plan_id=plan.id, product_id=product_id,
            material_node_id=material_id, department_node_id=department_id, task_quantity=quantity,
        ))
    session.flush()


def assembly_components(session, orders, routes, contexts):
    candidates = [order for order in orders if uses_assembly_tree(
        routes[route_key(order)].department_code)]
    assemblies = [order for order in candidates
                  if len(contexts[item_key(order)]["requirements"][order.material_node_id]) > 1]
    if not assemblies:
        return {}
    received = {(order_id, material): int(quantity) for order_id, material, quantity in session.execute(
        select_current(DepartmentWorkOrderMovement.work_order_id, DepartmentWorkOrderMovement.input_material_node_id,
               func.sum(DepartmentWorkOrderMovement.quantity))
        .where(DepartmentWorkOrderMovement.work_order_id.in_({order.id for order in assemblies}),
               DepartmentWorkOrderMovement.direction == "receipt")
        .group_by(DepartmentWorkOrderMovement.work_order_id, DepartmentWorkOrderMovement.input_material_node_id))}
    result = {}
    for order in assemblies:
        context = contexts[item_key(order)]
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
        conditions = [ProductionPlan.status != "draft", ProductionPlan.confirmed_at.is_not(None)]
        if work_order_id is None:
            conditions.append(~order_department_filter("warehouse"))
        if work_order_id is not None:
            conditions.append(DepartmentWorkOrder.id == work_order_id)
        if department_code is not None:
            conditions.append(order_department_filter(department_code))
        if plan_id is not None:
            conditions.append(ProductionPlan.id == plan_id)
        if order_no:
            conditions.append(ProductionPlan.order_no.ilike(f"%{order_no.strip()}%"))
        if product_keyword:
            conditions.append(order_product_filter(product_keyword))
        statement = (
            select_current(DepartmentWorkOrder, ProductionPlan)
            .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
            .where(*conditions)
        )
        total = session.scalar(select_current(func.count()).select_from(statement.subquery())) or 0
        rows = session.execute(
            statement.order_by(DepartmentWorkOrder.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return serialize_work_orders(session, rows, departments=departments), total


def route_neighbor_names(context):
    successors = context['routes'].successors
    predecessors = {key: set() for key in successors}
    for source, targets in successors.items():
        for target in targets:
            predecessors[target].add(source)
    labels = context['department_labels']
    return {key: {
        'upstream_departments': list(dict.fromkeys(labels[node_id] for _, node_id in sorted(predecessors[key]))),
        'downstream_departments': list(dict.fromkeys(labels[node_id] for _, node_id in sorted(targets))),
    } for key, targets in successors.items()}


def serialize_work_orders(session, rows, *, include_components=True, departments=None):
    if not rows:
        return []
    routes = route_references(session, route_keys={route_key(order) for order, plan in rows})
    items = snapshot_items(session, {item_key(order) for order, plan in rows})
    customers = customer_names_by_ids(session, {plan.customer_id for order, plan in rows})
    if departments is None:
        departments = department_names(session)
    if any(route_key(order) not in routes for order, plan in rows):
        raise DomainError("department_work_order_route_missing", "部门工单关联的计划快照路线不存在，请检查计划资料", status_code=409)
    orders = [order for order, plan in rows]
    contexts = {key: snapshot_context(item) for key, item in items.items()}
    neighbors = {key: route_neighbor_names(context) for key, context in contexts.items()}
    components = assembly_components(session, orders, routes, contexts) if include_components else {}
    totals = movement_totals(session, orders, contexts)
    quality = inspection_totals(session, {order.id for order in orders if requires_inspection(routes[route_key(order)].department_code)})
    dispatched = warehouse_dispatched(session, {order.id for order in orders if is_warehouse(routes[route_key(order)].department_code)})
    data = []
    for order, plan in rows:
        route = routes[route_key(order)]
        item = items[item_key(order)]
        product = item
        good, scrap, rework = quality.get(order.id, (0, 0, 0))
        data.append({
            **neighbors[item_key(order)][(order.material_node_id, order.department_node_id)],
            "id": order.id, "production_plan_id": plan.id, "material_node_id": order.material_node_id, "department_node_id": order.department_node_id,
            "order_no": plan.order_no, "customer_name": customers[plan.customer_id],
            "order_quantity": item.order_quantity,
            "product_id": order.product_id, "factory_code": product.factory_code,
            "product_name": product.product_name, "part_no": material_number(contexts[item_key(order)], order.material_node_id),
            "part_name": route.part_name, "department_code": route.department_code,
            "department_name": departments[route.department_code],
            "department_occurrence": contexts[item_key(order)]['department_occurrences'][order.department_node_id],
            "can_receive": allows_receipts(route.department_code),
            "can_issue": allows_manual_issue(route.department_code) and route.department_code != 'purchase',
            "requires_inspection": requires_inspection(route.department_code),
            "good_quantity": str(good), "scrap_quantity": str(scrap), "rework_quantity": str(rework),
            "task_quantity": order.task_quantity, "plan_status": plan.status,
            "scheduled_date": order.scheduled_date.isoformat() if order.scheduled_date else None,
            "schedule_revision": order.schedule_revision,
            "received_quantity": str(good + scrap + rework) if requires_inspection(route.department_code) else totals.get(order.id, ("0", "0"))[0],
            "issued_quantity": str(int(totals.get(order.id, ("0", "0"))[1]) + dispatched.get(order.id, 0)),
            "components": components.get(order.id, []),
        })
    return data
