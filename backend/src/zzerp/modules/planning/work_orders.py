"""Department work orders are derived assignments, without execution state."""

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.engineering.api import (
    appearance_names,
    current_route_references,
    get_product_references,
    handoff_contexts,
    matching_product_ids_query,
    validated_plan_routes,
)
from zzerp.modules.organization.api import allows_receipts, department_names, uses_assembly_tree
from zzerp.modules.planning.movement_totals import MovementTotals, load_movement_totals
from zzerp.modules.planning.persistence import (
    DepartmentWorkOrder,
    ProductionPlan,
    ProductionPlanItem,
)
from zzerp.modules.planning.queries import ensure_plan_without_movements
from zzerp.modules.planning.work_order_access import department_order_condition
from zzerp.modules.sales.api import customer_names_by_ids


def rebuild_work_orders(session, plan: ProductionPlan) -> None:
    ensure_plan_without_movements(session, plan.id)
    quantities = []
    items = list(
        session.scalars(
            select(ProductionPlanItem)
            .where(ProductionPlanItem.production_plan_id == plan.id)
            .order_by(ProductionPlanItem.product_id, ProductionPlanItem.appearance_id)
        )
    )
    if not items:
        raise DomainError("plan_products_required", "生产计划至少需要一个产品")
    for item in items:
        for route in validated_plan_routes(session, item.product_id, item.appearance_id).values():
            quantity = item.production_quantity * route.unit_requirement
            if not 0 < quantity <= 2147483647:
                raise DomainError("department_task_quantity_invalid", "部门任务数量超出允许范围")
            quantities.append(
                (
                    item.product_id,
                    item.appearance_id,
                    route.material_node_id,
                    route.department_node_id,
                    quantity,
                )
            )
    for product_id, appearance_id, material_id, department_id, quantity in quantities:
        session.add(
            DepartmentWorkOrder(
                production_plan_id=plan.id,
                product_id=product_id,
                appearance_id=appearance_id,
                material_node_id=material_id,
                department_node_id=department_id,
                task_quantity=quantity,
            )
        )
    session.flush()


def assembly_components(orders, routes, contexts, totals):
    candidates = [
        order
        for order in orders
        if uses_assembly_tree(
            routes[
                (
                    order.product_id,
                    order.appearance_id,
                    order.material_node_id,
                    order.department_node_id,
                )
            ].department_code
        )
    ]
    assemblies = [
        order
        for order in candidates
        if len(contexts[order.appearance_id].requirements[order.material_node_id]) > 1
    ]
    if not assemblies:
        return {}
    result = {}
    for order in assemblies:
        context = contexts[order.appearance_id]
        requirements = context.requirements[order.material_node_id]
        result[order.id] = [
            dict(
                material_node_id=part,
                part_no=context.parts[part].part_no,
                part_name=context.parts[part].part_name,
                required_quantity=str(order.task_quantity * requirements[part]),
                received_quantity=str(totals.get(order.id, MovementTotals()).receipts.get(part, 0)),
            )
            for part in sorted(requirements, key=lambda part: context.parts[part].part_no)
        ]
    return result


def list_work_orders(
    session: Session,
    page: int,
    page_size: int,
    *,
    department_scope: str | None,
    department_code: str | None = None,
    plan_id: int | None = None,
    work_order_id: int | None = None,
    order_no: str | None = None,
    product_keyword: str | None = None,
) -> tuple[list[dict], int]:
    if department_scope is not None:
        if department_code is not None and department_code != department_scope:
            raise DomainError("department_access_denied", "只能查看本部门工单", status_code=403)
        department_code = department_scope
    departments = department_names(session)
    if department_code is not None and department_code not in departments:
        raise DomainError("department_not_found", "生产部门不存在", status_code=404)
    conditions = []
    if work_order_id is not None:
        conditions.append(DepartmentWorkOrder.id == work_order_id)
    if department_code is not None:
        conditions.append(department_order_condition(department_code))
    if plan_id is not None:
        conditions.append(ProductionPlan.id == plan_id)
    if order_no:
        conditions.append(ProductionPlan.order_no.ilike(f"%{order_no.strip()}%"))
    if product_keyword:
        conditions.append(
            DepartmentWorkOrder.product_id.in_(matching_product_ids_query(product_keyword))
        )
    statement = (
        select(DepartmentWorkOrder, ProductionPlan)
        .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
        .where(*conditions)
    )
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.execute(
        statement.order_by(DepartmentWorkOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return serialize_work_orders(session, rows, departments=departments), total


def serialize_work_orders(session, rows, *, include_components=True, departments=None):
    if not rows:
        return []
    routes = current_route_references(
        session,
        route_keys={
            (
                order.product_id,
                order.appearance_id,
                order.material_node_id,
                order.department_node_id,
            )
            for order, plan in rows
        },
    )
    products = get_product_references(session, {order.product_id for order, plan in rows})
    items = {
        (item.production_plan_id, item.product_id, item.appearance_id): item
        for item in session.scalars(
            select(ProductionPlanItem).where(
                tuple_(
                    ProductionPlanItem.production_plan_id,
                    ProductionPlanItem.product_id,
                    ProductionPlanItem.appearance_id,
                ).in_(
                    {
                        (order.production_plan_id, order.product_id, order.appearance_id)
                        for order, plan in rows
                    }
                )
            )
        )
    }
    customers = customer_names_by_ids(session, {plan.customer_id for order, plan in rows})
    if departments is None:
        departments = department_names(session)
    if any(
        (order.product_id, order.appearance_id, order.material_node_id, order.department_node_id)
        not in routes
        for order, plan in rows
    ):
        raise DomainError(
            "department_work_order_route_missing",
            "部门工单关联的当前正式路线不存在，请检查工程资料",
            status_code=409,
        )
    orders = [order for order, plan in rows]
    contexts = handoff_contexts(session, {order.appearance_id for order in orders})
    totals = load_movement_totals(session, {order.id for order in orders})
    components = assembly_components(orders, routes, contexts, totals) if include_components else {}
    names = appearance_names(session, {order.appearance_id for order in orders})
    data = []
    for order, plan in rows:
        route = routes[
            (
                order.product_id,
                order.appearance_id,
                order.material_node_id,
                order.department_node_id,
            )
        ]
        product = products[order.product_id]
        item = items[(plan.id, order.product_id, order.appearance_id)]
        total = totals.get(order.id, MovementTotals())
        if set(total.receipts) <= {order.material_node_id}:
            received = str(total.receipts.get(order.material_node_id, 0))
        else:
            context = contexts[order.appearance_id]
            received = "；".join(
                f"{context.material_names[key]} {value}"
                for key, value in sorted(total.receipts.items())
            )
        data.append(
            {
                "id": order.id,
                "production_plan_id": plan.id,
                "material_node_id": order.material_node_id,
                "department_node_id": order.department_node_id,
                "order_no": plan.order_no,
                "customer_name": customers[plan.customer_id],
                "order_quantity": item.order_quantity,
                "product_id": order.product_id,
                "appearance_id": order.appearance_id,
                "appearance_name": names[order.appearance_id],
                "factory_code": product.factory_code,
                "product_name": product.product_name,
                "part_no": route.part_no,
                "part_name": route.part_name,
                "department_code": route.department_code,
                "department_name": departments[route.department_code],
                "can_receive": allows_receipts(route.department_code),
                "task_quantity": order.task_quantity,
                "plan_status": plan.status,
                "received_quantity": received,
                "issued_quantity": str(total.issued),
                "components": components.get(order.id, []),
            }
        )
    return data
