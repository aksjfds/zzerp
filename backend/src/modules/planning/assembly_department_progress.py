from __future__ import annotations

"""Department production-task dispatch and assembly-task query."""

from collections import defaultdict
from sqlalchemy import func, or_, select
from database import SessionLocal
from modules.engineering.model_api import Product, ProductBom
from modules.planning.persistence import ProductionPlan, ProductionPlanItem, ProductionRouteTask
from modules.planning.assembly_progress import assembly_arrival_progress, assembly_completion_summary
from modules.planning.department_progress import list_standard_department_progress
from modules.organization.model_api import Department, Workshop
from modules.production_core.model_api import ProductionItem, ProductionMovement, WorkOrder, WorkOrderBatch
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.production_core.operational_api import load_product_flow
from modules.planning.progress_calculations import _group, _process_completion_summary

def list_department_production_progress(
    department_code: str,
    page: int,
    page_size: int,
    keyword: str | None,
) -> tuple[list[dict], int]:
    if department_code == "assembly":
        return _list_assembly_production_progress(page, page_size, keyword)
    return list_standard_department_progress(
        department_code,
        page,
        page_size,
        keyword,
    )

def _list_assembly_production_progress(
    page: int,
    page_size: int,
    keyword: str | None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        workshops = {
            item.id: item for item in session.scalars(select(Workshop)).all()
        }
        assembly_department = session.scalar(
            select(Department).where(Department.department_code == "assembly")
        )
        if assembly_department is None:
            return [], 0
        normalized_keyword = (keyword or "").strip()
        candidate = (
            select(
                ProductionRouteTask.id.label("route_task_id"),
                CustomerOrder.created_at.label("order_created_at"),
                CustomerOrder.customer_order_no.label("order_no"),
                ProductionPlanItem.item_code.label("item_code"),
                ProductionPlanItem.id.label("plan_item_id"),
                ProductionRouteTask.route_order.label("route_order"),
            )
            .select_from(ProductionRouteTask)
            .join(
                ProductionPlanItem,
                ProductionPlanItem.id == ProductionRouteTask.production_plan_item_id,
            )
            .join(
                ProductionPlan,
                ProductionPlan.id == ProductionPlanItem.production_plan_id,
            )
            .join(
                CustomerOrderItem,
                CustomerOrderItem.id == ProductionPlanItem.customer_order_item_id,
            )
            .join(
                CustomerOrder,
                CustomerOrder.id == ProductionPlan.customer_order_id,
            )
            .join(Product, Product.id == ProductionPlanItem.product_id)
            .join(Workshop, Workshop.id == ProductionRouteTask.workshop_id)
            .where(
                Workshop.department_id == assembly_department.id,
                ProductionPlan.status.in_(("draft", "confirmed")),
                CustomerOrder.status != "cancelled",
                ProductionPlanItem.item_type == "assembly",
                ProductionPlanItem.planned_production_quantity > 0,
            )
        )
        if normalized_keyword:
            pattern = f"%{normalized_keyword}%"
            candidate = candidate.where(
                or_(
                    ProductionPlanItem.item_code.ilike(pattern),
                    ProductionPlanItem.item_name.ilike(pattern),
                    Product.factory_code.ilike(pattern),
                    Product.product_name.ilike(pattern),
                    CustomerOrder.customer_order_no.ilike(pattern),
                    Workshop.workshop_name.ilike(pattern),
                )
            )
        candidate_subquery = candidate.subquery()
        total = session.scalar(
            select(func.count()).select_from(candidate_subquery)
        ) or 0
        route_task_ids = list(
            session.scalars(
                select(candidate_subquery.c.route_task_id)
                .order_by(
                    candidate_subquery.c.order_created_at.desc(),
                    candidate_subquery.c.order_no.desc(),
                    candidate_subquery.c.item_code.desc(),
                    candidate_subquery.c.plan_item_id.desc(),
                    candidate_subquery.c.route_order,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        if not route_task_ids:
            return [], total
        context_rows = list(
            session.execute(
                select(
                    ProductionRouteTask,
                    ProductionPlanItem,
                    ProductionPlan,
                    CustomerOrderItem,
                    CustomerOrder,
                    Product,
                )
                .join(
                    ProductionPlanItem,
                    ProductionPlanItem.id
                    == ProductionRouteTask.production_plan_item_id,
                )
                .join(
                    ProductionPlan,
                    ProductionPlan.id
                    == ProductionPlanItem.production_plan_id,
                )
                .join(
                    CustomerOrderItem,
                    CustomerOrderItem.id
                    == ProductionPlanItem.customer_order_item_id,
                )
                .join(
                    CustomerOrder,
                    CustomerOrder.id == ProductionPlan.customer_order_id,
                )
                .join(Product, Product.id == ProductionPlanItem.product_id)
                .where(ProductionRouteTask.id.in_(route_task_ids))
            )
        )
        context_by_id = {row[0].id: row for row in context_rows}
        flow_cache: dict[tuple[int, int], tuple[dict, dict[str, dict]]] = {}
        tasks = []
        for route_task_id in route_task_ids:
            context_row = context_by_id.get(route_task_id)
            if context_row is None:
                continue
            (
                route_task,
                plan_item,
                plan,
                order_item,
                order,
                product,
            ) = context_row
            flow_key = (plan_item.product_id, plan_item.product_version)
            if flow_key not in flow_cache:
                flow_cache[flow_key] = load_product_flow(session, *flow_key)
            flow, nodes = flow_cache[flow_key]
            assembly_node = nodes.get(plan_item.flow_node_id)
            task_node = nodes.get(route_task.route_flow_node_id)
            if assembly_node is None or task_node is None:
                continue
            tasks.append(
                (
                    plan_item,
                    plan,
                    order_item,
                    order,
                    product,
                    flow,
                    nodes,
                    assembly_node,
                    task_node,
                )
            )
        if not tasks:
            return [], total

        order_item_ids = {
            order_item.id
            for _, _, order_item, *_rest in tasks
        }
        production_items = list(session.scalars(
            select(ProductionItem).where(
                ProductionItem.customer_order_item_id.in_(order_item_ids)
            )
        ).all())
        production_item_by_id = {item.id: item for item in production_items}
        production_items_by_order_item = _group(
            production_items,
            "customer_order_item_id",
        )
        production_item_ids = set(production_item_by_id)
        movements = list(session.scalars(
            select(ProductionMovement).where(
                ProductionMovement.production_item_id.in_(production_item_ids)
            )
        ).all()) if production_item_ids else []
        movements_by_order_item: dict[int, list[ProductionMovement]] = defaultdict(list)
        for movement in movements:
            production_item = production_item_by_id.get(movement.production_item_id)
            if production_item is not None:
                movements_by_order_item[production_item.customer_order_item_id].append(
                    movement
                )

        work_orders_by_task: dict[tuple[int, str], list[WorkOrder]] = defaultdict(list)
        work_orders = []
        if production_item_ids:
            for work_order, order_item_id in session.execute(
                select(WorkOrder, ProductionItem.customer_order_item_id)
                .join(
                    ProductionItem,
                    ProductionItem.id == WorkOrder.production_item_id,
                )
                .where(
                    ProductionItem.customer_order_item_id.in_(order_item_ids),
                    WorkOrder.status != "cancelled",
                )
            ):
                work_orders.append(work_order)
                work_orders_by_task[(order_item_id, work_order.flow_node_id)].append(
                    work_order
                )
        work_order_ids = {item.id for item in work_orders}
        batches_by_order: dict[int, list[WorkOrderBatch]] = defaultdict(list)
        if work_order_ids:
            for batch in session.scalars(
                select(WorkOrderBatch).where(
                    WorkOrderBatch.work_order_id.in_(work_order_ids)
                )
            ):
                batches_by_order[batch.work_order_id].append(batch)

        bom_items = {
            item.id: item
            for item in session.scalars(
                select(ProductBom).where(
                    ProductBom.product_id.in_(
                        {product.id for _, _, _, _, product, *_rest in tasks}
                    )
                )
            )
        }
        rows = []
        for (
            plan_item,
            _plan,
            order_item,
            order,
            product,
            flow,
            nodes,
            assembly_node,
            task_node,
        ) in tasks:
            output_unit_quantity = max(
                int(assembly_node.get("output_pcs") or 1),
                1,
            )
            remarks = [
                value.strip()
                for value in (order_item.remark, order.remark)
                if value and value.strip()
            ]
            output_item = next(
                (
                    item
                    for item in production_items_by_order_item.get(order_item.id, [])
                    if item.product_bom_id is None
                    and item.origin_flow_node_id == plan_item.flow_node_id
                ),
                None,
            )
            task_node_id = task_node["id"]
            task_workshop = workshops.get(task_node.get("workshop_id"))
            task_orders = work_orders_by_task.get(
                (order_item.id, task_node_id),
                [],
            )
            if task_node_id == plan_item.flow_node_id:
                completed_quantity = assembly_completion_summary(
                    task_orders,
                    batches_by_order,
                    output_unit_quantity,
                )
                arrived_quantity, material_arrivals = assembly_arrival_progress(
                    flow,
                    nodes,
                    plan_item.flow_node_id,
                    output_unit_quantity,
                    production_items_by_order_item.get(order_item.id, []),
                    movements_by_order_item.get(order_item.id, []),
                    bom_items,
                    plan_item.planned_production_quantity,
                )
            else:
                completed_quantity = _process_completion_summary(
                    task_orders,
                    batches_by_order,
                )
                arrived_quantity = sum(
                    movement.quantity
                    for movement in movements_by_order_item.get(order_item.id, [])
                    if movement.target_flow_node_id == task_node_id
                    and movement.source_flow_node_id != task_node_id
                )
                material_arrivals = []
            processing_workshop = (
                task_workshop.workshop_name
                if task_workshop else str(task_node.get("label") or "装配")
            )
            rows.append({
                "production_plan_item_id": plan_item.id,
                "production_item_id": output_item.id if output_item else None,
                "flow_node_id": task_node_id,
                "part_no": plan_item.item_code,
                "part_name": f"{product.product_name}-{plan_item.item_name}",
                "processing_workshop": processing_workshop,
                "task_quantity": plan_item.planned_production_quantity,
                "arrived_quantity": arrived_quantity,
                "material_arrivals": material_arrivals,
                "completed_quantity": completed_quantity,
                "remark": "；".join(dict.fromkeys(remarks)),
            })
        return rows, total
