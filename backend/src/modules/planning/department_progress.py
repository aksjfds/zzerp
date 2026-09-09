"""Department production-task read model optimized around production plans."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, or_, select

from database import SessionLocal
from modules.engineering.model_api import Product
from modules.organization.model_api import Department, Workshop
from modules.planning.persistence import (
    ProductionPlan,
    ProductionPlanItem,
    ProductionRouteTask,
)
from modules.planning.progress_calculations import released_task_quantity
from modules.planning.task_status_summary import (
    TaskAvailableSource,
    build_task_processing_statuses,
)
from modules.production_core.model_api import (
    MaterialProcessingState,
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
    WorkOrderBatch,
)
from modules.production_core.operational_api import load_product_flow
from modules.production_core.workbench_read_api import reserved_quantities
from modules.sales.model_api import Customer, CustomerOrder, CustomerOrderItem


_StandardTask = tuple[
    ProductionPlanItem,
    ProductionPlan,
    CustomerOrderItem,
    CustomerOrder,
    Product,
    dict[str, dict],
    Workshop,
    list[dict],
]


@dataclass(frozen=True, slots=True)
class _StandardTaskState:
    production_item_by_identity: dict[tuple, ProductionItem]
    movements_by_item: dict[int, list[ProductionMovement]]
    orders_by_item: dict[int, list[WorkOrder]]
    repositories_by_item: dict[int, list[Repository]]
    reserved_by_repository: dict[int, int]
    batches_by_order: dict[int, list[WorkOrderBatch]]
    processing_states: dict[int, MaterialProcessingState]


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
        route_task_ids, total = _standard_route_task_page(
            session,
            department.id,
            page,
            page_size,
            keyword,
        )
        if not route_task_ids:
            return [], total

        tasks = _load_standard_tasks(session, route_task_ids)
        state = _load_standard_task_state(session, tasks, department.id)
        return [_standard_task_row(task, state) for task in tasks], total


def _load_standard_tasks(session, route_task_ids: list[int]) -> list[_StandardTask]:
    context_rows = list(session.execute(
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
            ProductionRouteTask.id.in_(route_task_ids),
            ProductionRouteTask.route_node_type == "process",
        )
        .order_by(ProductionRouteTask.route_order)
    ))
    context_by_id = {row[0].id: row for row in context_rows}
    flow_cache: dict[tuple[int, int], tuple[dict, dict[str, dict]]] = {}
    tasks = []
    for route_task_id in route_task_ids:
        context = context_by_id.get(route_task_id)
        if context is None:
            continue
        route_task, plan_item, plan, order_item, order, product, workshop = context
        flow_key = (plan_item.product_id, plan_item.product_version)
        if flow_key not in flow_cache:
            flow_cache[flow_key] = load_product_flow(session, *flow_key)
        _flow, nodes = flow_cache[flow_key]
        tasks.append((
            plan_item,
            plan,
            order_item,
            order,
            product,
            nodes,
            workshop,
            [nodes[route_task.route_flow_node_id]],
        ))
    return tasks


def _load_standard_task_state(
    session,
    tasks: list[_StandardTask],
    department_id: int,
) -> _StandardTaskState:
    order_item_ids = {task[0].customer_order_item_id for task in tasks}
    production_items = list(session.scalars(
        select(ProductionItem).where(
            ProductionItem.customer_order_item_id.in_(order_item_ids)
        )
    ))
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
        for production_item in [production_item_by_identity.get(_plan_item_identity(plan_item))]
        if production_item is not None
    }
    movements_by_item: dict[int, list[ProductionMovement]] = defaultdict(list)
    if production_item_ids:
        for movement in session.scalars(
            select(ProductionMovement).where(
                ProductionMovement.production_item_id.in_(production_item_ids)
            )
        ):
            movements_by_item[movement.production_item_id].append(movement)
    work_orders = (
        list(session.scalars(
            select(WorkOrder).where(
                WorkOrder.production_item_id.in_(production_item_ids),
                WorkOrder.status != "cancelled",
            )
        ))
        if production_item_ids else []
    )
    orders_by_item: dict[int, list[WorkOrder]] = defaultdict(list)
    for work_order in work_orders:
        orders_by_item[work_order.production_item_id].append(work_order)
    repositories = (
        list(session.scalars(
            select(Repository).where(
                Repository.production_item_id.in_(production_item_ids),
                Repository.department_id == department_id,
            )
        ))
        if production_item_ids else []
    )
    repositories_by_item: dict[int, list[Repository]] = defaultdict(list)
    for repository in repositories:
        repositories_by_item[repository.production_item_id].append(repository)
    batches_by_order: dict[int, list[WorkOrderBatch]] = defaultdict(list)
    work_order_ids = {work_order.id for work_order in work_orders}
    if work_order_ids:
        for batch in session.scalars(
            select(WorkOrderBatch).where(WorkOrderBatch.work_order_id.in_(work_order_ids))
        ):
            batches_by_order[batch.work_order_id].append(batch)
    return _StandardTaskState(
        production_item_by_identity=production_item_by_identity,
        movements_by_item=movements_by_item,
        orders_by_item=orders_by_item,
        repositories_by_item=repositories_by_item,
        reserved_by_repository=reserved_quantities(
            session,
            [repository.id for repository in repositories],
        ),
        batches_by_order=batches_by_order,
        processing_states={
            state.id: state
            for state in session.scalars(
                select(MaterialProcessingState).where(
                    MaterialProcessingState.id.in_(
                        {repository.processing_state_id for repository in repositories}
                    )
                )
            )
        } if repositories else {},
    )


def _standard_task_row(task: _StandardTask, state: _StandardTaskState) -> dict:
    plan_item, plan, order_item, order, product, nodes, workshop, route_nodes = task
    production_item = state.production_item_by_identity.get(_plan_item_identity(plan_item))
    movements = (
        state.movements_by_item.get(production_item.id, [])
        if production_item is not None else []
    )
    work_orders = (
        state.orders_by_item.get(production_item.id, [])
        if production_item is not None else []
    )
    remarks = [
        value.strip()
        for value in (order_item.remark, order.remark)
        if value and value.strip()
    ]
    if production_item is None:
        remarks.append("等待前序生产")
    node_ids = {node["id"] for node in route_nodes}
    task_work_orders = [
        work_order for work_order in work_orders
        if work_order.flow_node_id in node_ids
    ]
    available_sources = _available_status_sources(
        (
            state.repositories_by_item.get(production_item.id, [])
            if production_item is not None else []
        ),
        state.reserved_by_repository,
        state.processing_states,
        node_ids,
    )
    arrived_quantity = _node_arrived_quantity(movements, node_ids)
    completed_quantity = released_task_quantity(
        movements,
        task_work_orders,
        route_nodes[0]["id"],
        nodes,
    )
    return {
        "production_plan_item_id": plan_item.id,
        "customer_order_item_id": plan_item.customer_order_item_id,
        "customer_order_no": order.customer_order_no,
        "production_item_id": production_item.id if production_item is not None else None,
        "flow_node_id": route_nodes[0]["id"],
        "plan_status": plan.status,
        "part_no": plan_item.item_code,
        "part_name": f"{product.product_name}-{plan_item.item_name}",
        "processing_workshop_id": workshop.id,
        "processing_workshop": workshop.workshop_name,
        "task_quantity": plan_item.planned_production_quantity,
        "arrived_quantity": arrived_quantity,
        "material_arrivals": [],
        "processing_statuses": build_task_processing_statuses(
            task_work_orders,
            state.batches_by_order,
            available_sources=available_sources,
            task_quantity=plan_item.planned_production_quantity,
            completed_quantity=completed_quantity,
        ),
        "completed_quantity": completed_quantity,
        "remark": "；".join(dict.fromkeys(remarks)),
    }


def _plan_item_identity(plan_item: ProductionPlanItem) -> tuple:
    return (
        plan_item.customer_order_item_id,
        plan_item.product_id,
        plan_item.product_version,
        plan_item.product_bom_id,
        plan_item.flow_node_id,
    )


def _standard_route_task_page(
    session,
    department_id: int,
    page: int,
    page_size: int,
    keyword: str | None,
) -> tuple[list[int], int]:
    candidate = (
        select(
            ProductionRouteTask.id.label("route_task_id"),
            ProductionRouteTask.production_plan_item_id.label("plan_item_id"),
            CustomerOrder.created_at.label("order_created_at"),
            CustomerOrder.customer_order_no.label("order_no"),
            ProductionPlanItem.item_code.label("item_code"),
            ProductionRouteTask.route_order.label("route_order"),
        )
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
        .join(Customer, Customer.id == CustomerOrder.customer_id)
        .join(Product, Product.id == ProductionPlanItem.product_id)
        .join(Workshop, Workshop.id == ProductionRouteTask.workshop_id)
        .where(
            Workshop.department_id == department_id,
            ProductionRouteTask.route_node_type == "process",
            ProductionPlan.status.in_(("confirmed", "completed")),
            CustomerOrder.status != "cancelled",
            ProductionPlanItem.item_type.in_(("part", "assembly")),
            ProductionPlanItem.planned_production_quantity > 0,
        )
    )
    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        candidate = candidate.where(or_(
            ProductionPlanItem.item_code.ilike(pattern),
            ProductionPlanItem.item_name.ilike(pattern),
            Product.factory_code.ilike(pattern),
            Product.product_name.ilike(pattern),
            CustomerOrder.customer_order_no.ilike(pattern),
            Customer.customer_name.ilike(pattern),
            Workshop.workshop_name.ilike(pattern),
        ))
    candidate_subquery = candidate.subquery()
    total = int(
        session.scalar(select(func.count()).select_from(candidate_subquery)) or 0
    )
    route_task_ids = list(session.scalars(
        select(candidate_subquery.c.route_task_id)
        .order_by(
            candidate_subquery.c.order_created_at.desc(),
            candidate_subquery.c.order_no.desc(),
            candidate_subquery.c.item_code.desc(),
            candidate_subquery.c.plan_item_id.desc(),
            candidate_subquery.c.route_order,
            candidate_subquery.c.route_task_id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ))
    return route_task_ids, total


def _node_arrived_quantity(
    movements: list[ProductionMovement],
    target_node_ids: set[str],
) -> int:
    return sum(
        movement.quantity
        for movement in movements
        if movement.target_flow_node_id in target_node_ids
        and movement.source_flow_node_id not in target_node_ids
    )


def _available_status_sources(
    repositories: list[Repository],
    reserved_by_repository: dict[int, int],
    processing_states: dict[int, MaterialProcessingState],
    task_node_ids: set[str],
) -> list[TaskAvailableSource]:
    sources = []
    for repository in repositories:
        available_quantity = (
            repository.quantity
            - reserved_by_repository.get(repository.id, 0)
        )
        if (
            repository.flow_node_id not in task_node_ids
            or available_quantity <= 0
        ):
            continue
        processing_state = processing_states[repository.processing_state_id]
        sources.append(TaskAvailableSource(
            repository_id=repository.id,
            processing_status=processing_state.display_text,
            has_current_position_processing=any(
                history.get("flow_node_id") in task_node_ids
                for history in processing_state.procedure_history
            ),
            creation_mode="repository",
            quantity=available_quantity,
        ))
    return sources


__all__ = ["list_standard_department_progress"]
