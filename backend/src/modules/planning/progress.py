"""Plan-paged, read-only production progress from real department orders."""

from sqlalchemy import func, select

from database import SessionLocal
from modules.engineering.product_reference_api import matching_product_ids
from modules.engineering.route_api import current_department_orders
from modules.errors import DomainError
from modules.planning.persistence import DepartmentWorkOrder, ProductionPlan
from modules.planning.work_orders import serialize_work_orders


def group_progress(orders, route_orders, product_ids):
    products = {}
    for order in orders:
        product = products.setdefault(order["product_id"], dict(product_id=order["product_id"],
            factory_code=order["factory_code"], product_name=order["product_name"], materials={}))
        material = product["materials"].setdefault(order["material_node_id"], dict(
            material_node_id=order["material_node_id"], part_no=order["part_no"],
            part_name=order["part_name"], work_orders=[]))
        material["work_orders"].append(order)
    result = []
    for product_id in product_ids:
        if product_id not in products:
            continue
        product = products[product_id]
        ranks = route_orders[product_id]
        materials = list(product["materials"].values())
        for material in materials:
            if any(order["department_node_id"] not in ranks for order in material["work_orders"]):
                raise DomainError("progress_route_missing", "工单部门不在当前正式流程中", status_code=409)
            material["work_orders"].sort(key=lambda order: (
                ranks[order["department_node_id"]], order["id"]))
        materials.sort(key=lambda material: (
            min(ranks[order["department_node_id"]] for order in material["work_orders"]),
            material["part_no"], material["material_node_id"]))
        product["materials"] = materials
        result.append(product)
    return result


def list_production_progress(page, page_size, *, department_scope, order_no=None, product_keyword=None):
    if department_scope is not None:
        raise DomainError("progress_access_denied", "生产账号仅可查看所属部门工单", status_code=403)
    with SessionLocal() as session:
        conditions = []
        if order_no:
            conditions.append(ProductionPlan.order_no.ilike(f"%{order_no.strip()}%"))
        if product_keyword:
            conditions.append(DepartmentWorkOrder.product_id.in_(matching_product_ids(session, product_keyword)))
        plan_query = (select(ProductionPlan.id)
            .join(DepartmentWorkOrder, DepartmentWorkOrder.production_plan_id == ProductionPlan.id)
            .where(*conditions).distinct().subquery())
        total = session.scalar(select(func.count()).select_from(plan_query)) or 0
        plan_ids = list(session.scalars(select(plan_query.c.id)
            .order_by(plan_query.c.id.desc()).offset((page-1)*page_size).limit(page_size)))
        if not plan_ids:
            return [], total
        rows = session.execute(select(DepartmentWorkOrder, ProductionPlan)
            .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
            .where(*conditions, ProductionPlan.id.in_(plan_ids))).all()
        orders = serialize_work_orders(session, rows, include_components=False)
        product_ids = {order["product_id"] for order in orders}
        route_orders = current_department_orders(session, set(product_ids))
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
        products = sorted({order["product_id"] for order in plan_orders})
        result.append(dict(production_plan_id=plan_id, order_no=plan_orders[0]["order_no"],
            customer_name=plan_orders[0]["customer_name"],
            products=group_progress(plan_orders, route_orders, products)))
    return result
