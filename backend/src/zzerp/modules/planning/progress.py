"""Plan-paged, read-only production progress from real department orders."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.engineering.api import current_department_orders, matching_product_ids_query
from zzerp.modules.planning.persistence import DepartmentWorkOrder, ProductionPlan
from zzerp.modules.planning.work_orders import serialize_work_orders


def group_progress(orders, route_orders, product_ids):
    products = {}
    for order in orders:
        product = products.setdefault(
            (order["product_id"], order["appearance_id"]),
            dict(
                product_id=order["product_id"],
                appearance_id=order["appearance_id"],
                appearance_name=order["appearance_name"],
                factory_code=order["factory_code"],
                product_name=order["product_name"],
                materials={},
            ),
        )
        material = product["materials"].setdefault(
            order["material_node_id"],
            dict(
                material_node_id=order["material_node_id"],
                part_no=order["part_no"],
                part_name=order["part_name"],
                work_orders=[],
            ),
        )
        material["work_orders"].append(order)
    result = []
    for product_id in product_ids:
        if product_id not in products:
            continue
        product = products[product_id]
        ranks = route_orders[product_id[1]]
        materials = list(product["materials"].values())
        for material in materials:
            if any(order["department_node_id"] not in ranks for order in material["work_orders"]):
                raise DomainError(
                    "progress_route_missing", "工单部门不在当前正式流程中", status_code=409
                )
            material["work_orders"].sort(
                key=lambda order: (ranks[order["department_node_id"]], order["id"])
            )
        materials.sort(
            key=lambda material: (
                min(ranks[order["department_node_id"]] for order in material["work_orders"]),
                material["part_no"],
                material["material_node_id"],
            )
        )
        product["materials"] = materials
        result.append(product)
    return result


def list_production_progress(
    session: Session, page, page_size, *, department_scope, order_no=None, product_keyword=None
):
    if department_scope is not None:
        raise DomainError("progress_access_denied", "生产账号仅可查看所属部门工单", status_code=403)
    plan_conditions = []
    order_conditions = []
    if order_no:
        plan_conditions.append(ProductionPlan.order_no.ilike(f"%{order_no.strip()}%"))
    if product_keyword:
        order_conditions.append(
            DepartmentWorkOrder.product_id.in_(matching_product_ids_query(product_keyword))
        )
    plan_query = (
        select(ProductionPlan.id)
        .where(
            *plan_conditions,
            select(DepartmentWorkOrder.id)
            .where(
                DepartmentWorkOrder.production_plan_id == ProductionPlan.id,
                *order_conditions,
            )
            .exists(),
        )
        .subquery()
    )
    total = session.scalar(select(func.count()).select_from(plan_query)) or 0
    plan_ids = list(
        session.scalars(
            select(plan_query.c.id)
            .order_by(plan_query.c.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    if not plan_ids:
        return [], total
    rows = session.execute(
        select(DepartmentWorkOrder, ProductionPlan)
        .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
        .where(*order_conditions, ProductionPlan.id.in_(plan_ids))
    ).all()
    orders = serialize_work_orders(session, rows, include_components=False)
    route_orders = current_department_orders(session, {o["appearance_id"] for o in orders})
    return group_plan_progress(orders, route_orders, plan_ids), total


def group_plan_progress(orders, route_orders, plan_ids):
    by_plan = {}
    for order in orders:
        by_plan.setdefault(order["production_plan_id"], []).append(order)
    result = []
    for plan_id in plan_ids:
        plan_orders = by_plan.get(plan_id, [])
        if not plan_orders:
            continue
        products = sorted({(order["product_id"], order["appearance_id"]) for order in plan_orders})
        result.append(
            dict(
                production_plan_id=plan_id,
                order_no=plan_orders[0]["order_no"],
                customer_name=plan_orders[0]["customer_name"],
                products=group_progress(plan_orders, route_orders, products),
            )
        )
    return result
