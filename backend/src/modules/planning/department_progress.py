"""Department production-task read model optimized around production plans."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, or_, select, tuple_

from database import SessionLocal
from modules.engineering.model_api import Product
from modules.organization.model_api import Department, Workshop
from modules.planning.persistence import (
    ProductionPlan,
    ProductionPlanItem,
    ProductionRouteTask,
)
from modules.production_core.model_api import (
    ProductionItem,
    ProductionMovement,
    WorkOrder,
    WorkOrderBatch,
)
from modules.production_core.operational_api import (
    calculate_work_order_progress,
    load_product_flow,
)
from modules.sales.model_api import Customer, CustomerOrder, CustomerOrderItem


def list_standard_department_progress(
    department_code: str,
    page: int,
    page_size: int,
    keyword: str | None,
) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(
                Department.department_code == department_code
            )
        )
        if department is None:
            return [], 0
        normalized_keyword = (keyword or "").strip()
        candidate = (
            select(
                ProductionRouteTask.production_plan_item_id.label("plan_item_id"),
                ProductionRouteTask.workshop_id.label("workshop_id"),
                func.max(CustomerOrder.created_at).label("order_created_at"),
                func.max(CustomerOrder.customer_order_no).label("order_no"),
                func.max(ProductionPlanItem.item_code).label("item_code"),
                func.min(ProductionRouteTask.route_order).label("route_order"),
            )
            .join(
                ProductionPlanItem,
                ProductionPlanItem.id
                == ProductionRouteTask.production_plan_item_id,
            )
            .join(
                ProductionPlan,
                ProductionPlan.id == ProductionPlanItem.production_plan_id,
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
            .join(Customer, Customer.id == CustomerOrder.customer_id)
            .join(Product, Product.id == ProductionPlanItem.product_id)
            .join(Workshop, Workshop.id == ProductionRouteTask.workshop_id)
            .where(
                Workshop.department_id == department.id,
                ProductionRouteTask.route_node_type == "process",
                ProductionPlan.status.in_(("draft", "confirmed", "completed")),
                CustomerOrder.status != "cancelled",
                ProductionPlanItem.item_type.in_(("part", "assembly")),
                ProductionPlanItem.planned_production_quantity > 0,
            )
            .group_by(
                ProductionRouteTask.production_plan_item_id,
                ProductionRouteTask.workshop_id,
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
                    Customer.customer_name.ilike(pattern),
                    Workshop.workshop_name.ilike(pattern),
                )
            )
        candidate_subquery = candidate.subquery()
        total = (
            session.scalar(select(func.count()).select_from(candidate_subquery))
            or 0
        )
        page_pairs = list(
            session.execute(
                select(
                    candidate_subquery.c.plan_item_id,
                    candidate_subquery.c.workshop_id,
                )
                .order_by(
                    candidate_subquery.c.order_created_at.desc(),
                    candidate_subquery.c.order_no.desc(),
                    candidate_subquery.c.item_code.desc(),
                    candidate_subquery.c.plan_item_id.desc(),
                    candidate_subquery.c.route_order,
                    candidate_subquery.c.workshop_id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        if not page_pairs:
            return [], total

        pair_keys = [
            (int(row.plan_item_id), int(row.workshop_id))
            for row in page_pairs
        ]
        context_rows = session.execute(
            select(
                ProductionRouteTask,
                ProductionPlanItem,
                ProductionPlan,
                CustomerOrderItem,
                CustomerOrder,
                Product,
                Workshop,
            )
            .join(
                ProductionPlanItem,
                ProductionPlanItem.id
                == ProductionRouteTask.production_plan_item_id,
            )
            .join(
                ProductionPlan,
                ProductionPlan.id == ProductionPlanItem.production_plan_id,
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
            .join(Workshop, Workshop.id == ProductionRouteTask.workshop_id)
            .where(
                tuple_(
                    ProductionRouteTask.production_plan_item_id,
                    ProductionRouteTask.workshop_id,
                ).in_(pair_keys),
                ProductionRouteTask.route_node_type == "process",
            )
            .order_by(ProductionRouteTask.route_order)
        )
        grouped_context: dict[tuple[int, int], list[tuple]] = defaultdict(list)
        for row in context_rows:
            grouped_context[
                (row[0].production_plan_item_id, row[0].workshop_id)
            ].append(row)
        flow_cache: dict[tuple[int, int], tuple[dict, dict[str, dict]]] = {}
        tasks = []
        for pair_key in pair_keys:
            rows_for_pair = grouped_context.get(pair_key, [])
            if not rows_for_pair:
                continue
            (
                _route_task,
                plan_item,
                plan,
                order_item,
                order,
                product,
                workshop,
            ) = rows_for_pair[0]
            flow_key = (plan_item.product_id, plan_item.product_version)
            if flow_key not in flow_cache:
                flow_cache[flow_key] = load_product_flow(session, *flow_key)
            _flow, nodes = flow_cache[flow_key]
            route_nodes = [nodes[row[0].route_flow_node_id] for row in rows_for_pair]
            tasks.append((
                plan_item,
                plan,
                order_item,
                order,
                product,
                nodes,
                workshop,
                route_nodes,
            ))

        order_item_ids = {item[0].customer_order_item_id for item in tasks}
        production_items = list(
            session.scalars(
                select(ProductionItem).where(
                    ProductionItem.customer_order_item_id.in_(order_item_ids)
                )
            )
        )
        production_item_by_identity = {
            (
                item.customer_order_item_id,
                item.product_id,
                item.product_version,
                item.product_bom_id,
                item.origin_flow_node_id,
            ): item
            for item in production_items
        }
        production_item_ids = {
            production_item.id
            for plan_item, *_rest in tasks
            for production_item in [
                production_item_by_identity.get(
                    (
                        plan_item.customer_order_item_id,
                        plan_item.product_id,
                        plan_item.product_version,
                        plan_item.product_bom_id,
                        plan_item.flow_node_id,
                    )
                )
            ]
            if production_item is not None
        }
        movements_by_item: dict[int, list[ProductionMovement]] = defaultdict(list)
        if production_item_ids:
            for movement in session.scalars(
                select(ProductionMovement).where(
                    ProductionMovement.production_item_id.in_(
                        production_item_ids
                    )
                )
            ):
                movements_by_item[movement.production_item_id].append(movement)

        orders_by_item: dict[int, list[WorkOrder]] = defaultdict(list)
        work_orders = []
        if production_item_ids:
            work_orders = list(
                session.scalars(
                    select(WorkOrder).where(
                        WorkOrder.production_item_id.in_(production_item_ids),
                        WorkOrder.status != "cancelled",
                    )
                )
            )
            for work_order in work_orders:
                orders_by_item[work_order.production_item_id].append(work_order)
        batches_by_order: dict[int, list[WorkOrderBatch]] = defaultdict(list)
        work_order_ids = {item.id for item in work_orders}
        if work_order_ids:
            for batch in session.scalars(
                select(WorkOrderBatch).where(
                    WorkOrderBatch.work_order_id.in_(work_order_ids)
                )
            ):
                batches_by_order[batch.work_order_id].append(batch)

        rows = []
        for (
            plan_item,
            plan,
            order_item,
            order,
            product,
            nodes,
            workshop,
            route_nodes,
        ) in tasks:
            production_item = production_item_by_identity.get(
                (
                    plan_item.customer_order_item_id,
                    plan_item.product_id,
                    plan_item.product_version,
                    plan_item.product_bom_id,
                    plan_item.flow_node_id,
                )
            )
            movements = (
                movements_by_item.get(production_item.id, [])
                if production_item is not None
                else []
            )
            work_orders_for_item = (
                orders_by_item.get(production_item.id, [])
                if production_item is not None
                else []
            )
            remarks = [
                value.strip()
                for value in (order_item.remark, order.remark)
                if value and value.strip()
            ]
            if production_item is None:
                remarks.append(
                    "生产计划待确认"
                    if plan.status == "draft"
                    else "等待前序生产"
                )
            node_ids = {node["id"] for node in route_nodes}
            arrived_quantity = _workshop_arrived_quantity(
                movements,
                nodes,
                node_ids,
                workshop.id,
            )
            completed_quantity = _workshop_completed_quantity(
                work_orders_for_item,
                batches_by_order,
                node_ids,
            )
            rows.append(
                {
                    "production_plan_item_id": plan_item.id,
                    "production_item_id": (
                        production_item.id
                        if production_item is not None
                        else None
                    ),
                    "flow_node_id": None,
                    "part_no": plan_item.item_code,
                    "part_name": (
                        f"{product.product_name}-{plan_item.item_name}"
                    ),
                    "processing_workshop": (
                        workshop.workshop_name
                    ),
                    "task_quantity": plan_item.planned_production_quantity,
                    "arrived_quantity": arrived_quantity,
                    "material_arrivals": [],
                    "completed_quantity": completed_quantity,
                    "remark": "；".join(dict.fromkeys(remarks)),
                }
            )
        return rows, total


def _workshop_arrived_quantity(
    movements: list[ProductionMovement],
    nodes: dict[str, dict],
    target_node_ids: set[str],
    workshop_id: int,
) -> int:
    return sum(
        movement.quantity
        for movement in movements
        if movement.target_flow_node_id in target_node_ids
        and nodes.get(movement.source_flow_node_id or "", {}).get("workshop_id")
        != workshop_id
    )


def _workshop_completed_quantity(
    work_orders: list[WorkOrder],
    batches_by_order: dict[int, list[WorkOrderBatch]],
    flow_node_ids: set[str],
) -> int:
    completed_by_operation: dict[tuple[str, int], int] = defaultdict(int)
    for work_order in work_orders:
        if work_order.flow_node_id not in flow_node_ids:
            continue
        progress = calculate_work_order_progress(
            work_order,
            batches_by_order.get(work_order.id, []),
        )
        completed_by_operation[
            (work_order.flow_node_id, work_order.procedure_id)
        ] += progress.qualified_quantity
    return max(completed_by_operation.values(), default=0)


__all__ = ["list_standard_department_progress"]
