"""Plan-paged, read-only production progress from real department orders."""

from database import SessionLocal
from sqlalchemy import func, select

from modules.errors import DomainError
from modules.planning.completion import completed_quantities
from modules.planning.persistence import (
    DepartmentWorkOrder,
    ProductionPlan,
    ProductionPlanItem,
)
from modules.planning.snapshots import (
    item_key,
    order_department_filter,
    order_product_filter,
    snapshot_department_orders,
)
from modules.planning.work_orders import serialize_work_orders


def group_progress(orders, route_orders, product_ids, production_quantities):
    products = {}
    for order in orders:
        product = products.setdefault(order["product_id"], {"product_id": order["product_id"],
            "factory_code": order["factory_code"], "product_name": order["product_name"],
            "order_quantity": order["order_quantity"],
            "task_quantity": production_quantities[order["product_id"]], "materials": {}})
        material = product["materials"].setdefault(order["material_node_id"], {
            "material_node_id": order["material_node_id"], "part_no": order["part_no"],
            "part_name": order["part_name"], "order_quantity": order["order_quantity"],
            "task_quantity": order["task_quantity"], "work_orders": []})
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
                raise DomainError("progress_route_missing", "工单部门不在计划快照流程中", status_code=409)
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
        conditions = [ProductionPlan.status != "draft", ProductionPlan.confirmed_at.is_not(None),
                      ~order_department_filter("warehouse")]
        if order_no:
            conditions.append(ProductionPlan.order_no.ilike(f"%{order_no.strip()}%"))
        if product_keyword:
            conditions.append(order_product_filter(product_keyword))
        plan_query = (select(ProductionPlan.id)
            .join(DepartmentWorkOrder, DepartmentWorkOrder.production_plan_id == ProductionPlan.id)
            .where(*conditions).distinct().subquery())
        total = session.scalar(select(func.count()).select_from(plan_query)) or 0
        plan_ids = list(session.scalars(select(plan_query.c.id)
            .order_by(plan_query.c.id.desc()).offset((page-1)*page_size).limit(page_size)))
        if not plan_ids:
            return [], total
        rows = session.execute(select(DepartmentWorkOrder, ProductionPlan, ProductionPlanItem.production_quantity)
            .select_from(DepartmentWorkOrder)
            .join(ProductionPlan, ProductionPlan.id == DepartmentWorkOrder.production_plan_id)
            .join(ProductionPlanItem,
                  (ProductionPlanItem.production_plan_id == DepartmentWorkOrder.production_plan_id)
                  & (ProductionPlanItem.product_id == DepartmentWorkOrder.product_id))
            .where(*conditions, ProductionPlan.id.in_(plan_ids))).all()
        production_quantities = {(plan.id, order.product_id): quantity for order, plan, quantity in rows}
        rows = [(order, plan) for order, plan, quantity in rows]
        orders = serialize_work_orders(session, rows, include_components=False)
        route_orders = snapshot_department_orders(session, {item_key(order) for order, plan in rows})
        progress = group_plan_progress(orders, route_orders, plan_ids, production_quantities)
        completed = completed_quantities(session, orders)
        for plan in progress:
            for product in plan['products']:
                product['completed_quantity'] = str(completed.get((plan['production_plan_id'], product['product_id']), 0))
        return progress, total


def group_plan_progress(orders, route_orders, plan_ids, production_quantities):
    by_plan = {}
    for order in orders:
        by_plan.setdefault(order["production_plan_id"], []).append(order)
    result = []
    for plan_id in plan_ids:
        plan_orders = by_plan.get(plan_id, [])
        if not plan_orders:
            continue
        products = sorted({order["product_id"] for order in plan_orders})
        result.append({"production_plan_id": plan_id, "order_no": plan_orders[0]["order_no"],
            "customer_name": plan_orders[0]["customer_name"],
            "products": group_progress(plan_orders, {product_id: route_orders[(plan_id, product_id)] for product_id in products}, products,
                {product_id: production_quantities[(plan_id, product_id)] for product_id in products})})
    return result
