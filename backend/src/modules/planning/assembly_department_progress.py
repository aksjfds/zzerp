from __future__ import annotations

"""Department production-task dispatch and assembly-task query."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.material_identity import production_item_material_key
from modules.engineering.model_api import Product, ProductBom
from modules.organization.model_api import Department, Workshop
from modules.planning.assembly_progress import assembly_arrival_progress
from modules.planning.assembly_input_projection import normal_input_material_keys
from modules.planning.department_progress import list_standard_department_progress
from modules.planning.plan_builder import planned_product_quantity
from modules.planning.persistence import (
    ProductionPlan,
    ProductionPlanItem,
    ProductionRouteTask,
)
from modules.planning.progress_calculations import (
    _group,
    released_task_quantity,
)
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
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


@dataclass(frozen=True, slots=True)
class _AssemblyTask:
    plan_item: ProductionPlanItem
    plan: ProductionPlan
    order_item: CustomerOrderItem
    order: CustomerOrder
    product: Product
    flow: dict
    nodes: dict[str, dict]
    assembly_node: dict
    task_node: dict


@dataclass(frozen=True, slots=True)
class _AssemblyProgressState:
    workshops: dict[int, Workshop]
    planned_quantities: dict[int, int]
    item_by_id: dict[int, ProductionItem]
    items_by_order_item: dict[int, list[ProductionItem]]
    movements_by_order_item: dict[int, list[ProductionMovement]]
    orders_by_task: dict[tuple[int, str], list[WorkOrder]]
    batches_by_order: dict[int, list[WorkOrderBatch]]
    repositories_by_order_item: dict[int, list[Repository]]
    reserved_by_repository: dict[int, int]
    bom_items: dict[int, ProductBom]
    processing_states: dict[int, MaterialProcessingState]


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
        department = session.scalar(
            select(Department).where(Department.department_code == "assembly")
        )
        if department is None:
            return [], 0
        route_task_ids, total = _assembly_route_task_page(
            session, department.id, page, page_size, keyword
        )
        if not route_task_ids:
            return [], total
        tasks = _load_assembly_tasks(session, route_task_ids)
        if not tasks:
            return [], total
        state = _load_assembly_progress_state(session, tasks, department.id)
        return [_assembly_task_row(task, state) for task in tasks], total


def _assembly_route_task_page(
    session: Session,
    department_id: int,
    page: int,
    page_size: int,
    keyword: str | None,
) -> tuple[list[int], int]:
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
        .join(ProductionPlan, ProductionPlan.id == ProductionPlanItem.production_plan_id)
        .join(
            CustomerOrderItem,
            CustomerOrderItem.id == ProductionPlanItem.customer_order_item_id,
        )
        .join(CustomerOrder, CustomerOrder.id == ProductionPlan.customer_order_id)
        .join(Product, Product.id == ProductionPlanItem.product_id)
        .join(Workshop, Workshop.id == ProductionRouteTask.workshop_id)
        .where(
            Workshop.department_id == department_id,
            ProductionPlan.status.in_(("confirmed", "completed")),
            CustomerOrder.status != "cancelled",
            ProductionPlanItem.item_type == "assembly",
            ProductionPlanItem.planned_production_quantity > 0,
        )
    )
    normalized_keyword = (keyword or "").strip()
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
    candidates = candidate.subquery()
    total = session.scalar(select(func.count()).select_from(candidates)) or 0
    route_task_ids = list(
        session.scalars(
            select(candidates.c.route_task_id)
            .order_by(
                candidates.c.order_created_at.desc(),
                candidates.c.order_no.desc(),
                candidates.c.item_code.desc(),
                candidates.c.plan_item_id.desc(),
                candidates.c.route_order,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return route_task_ids, total


def _load_assembly_tasks(
    session: Session,
    route_task_ids: list[int],
) -> list[_AssemblyTask]:
    rows = session.execute(
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
            ProductionPlanItem.id == ProductionRouteTask.production_plan_item_id,
        )
        .join(ProductionPlan, ProductionPlan.id == ProductionPlanItem.production_plan_id)
        .join(
            CustomerOrderItem,
            CustomerOrderItem.id == ProductionPlanItem.customer_order_item_id,
        )
        .join(CustomerOrder, CustomerOrder.id == ProductionPlan.customer_order_id)
        .join(Product, Product.id == ProductionPlanItem.product_id)
        .where(ProductionRouteTask.id.in_(route_task_ids))
    )
    row_by_id = {row[0].id: row for row in rows}
    flow_cache: dict[tuple[int, int], tuple[dict, dict[str, dict]]] = {}
    tasks = []
    for route_task_id in route_task_ids:
        row = row_by_id.get(route_task_id)
        if row is None:
            continue
        route_task, plan_item, plan, order_item, order, product = row
        flow_key = (plan_item.product_id, plan_item.product_version)
        if flow_key not in flow_cache:
            flow_cache[flow_key] = load_product_flow(session, *flow_key)
        flow, nodes = flow_cache[flow_key]
        assembly_node = nodes.get(plan_item.flow_node_id)
        task_node = nodes.get(route_task.route_flow_node_id)
        if assembly_node is None or task_node is None:
            continue
        tasks.append(
            _AssemblyTask(
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
    return tasks


def _load_assembly_progress_state(
    session: Session,
    tasks: list[_AssemblyTask],
    department_id: int,
) -> _AssemblyProgressState:
    order_item_ids = {task.order_item.id for task in tasks}
    plan_items = list(
        session.scalars(
            select(ProductionPlanItem).where(
                ProductionPlanItem.customer_order_item_id.in_(order_item_ids)
            )
        )
    )
    planned_quantities = {
        item_id: planned_product_quantity(items)
        for item_id, items in _group(
            plan_items, "customer_order_item_id"
        ).items()
    }
    production_items = list(
        session.scalars(
            select(ProductionItem).where(
                ProductionItem.customer_order_item_id.in_(order_item_ids)
            )
        )
    )
    item_by_id = {item.id: item for item in production_items}
    item_ids = set(item_by_id)
    movements = (
        list(
            session.scalars(
                select(ProductionMovement).where(
                    ProductionMovement.production_item_id.in_(item_ids)
                )
            )
        )
        if item_ids
        else []
    )
    movements_by_order_item: dict[int, list[ProductionMovement]] = defaultdict(list)
    for movement in movements:
        order_item_id = item_by_id[
            movement.production_item_id
        ].customer_order_item_id
        movements_by_order_item[order_item_id].append(movement)
    orders_by_task, work_orders = _load_assembly_work_orders(
        session, order_item_ids
    )
    batches_by_order = _load_batches_by_order(
        session, {item.id for item in work_orders}
    )
    repositories = _load_assembly_repositories(session, item_ids, department_id)
    repositories_by_order_item: dict[int, list[Repository]] = defaultdict(list)
    for repository in repositories:
        order_item_id = item_by_id[
            repository.production_item_id
        ].customer_order_item_id
        repositories_by_order_item[order_item_id].append(repository)
    product_ids = {task.product.id for task in tasks}
    bom_items = {
        item.id: item
        for item in session.scalars(
            select(ProductBom).where(ProductBom.product_id.in_(product_ids))
        )
    }
    return _AssemblyProgressState(
        workshops={
            item.id: item for item in session.scalars(select(Workshop)).all()
        },
        planned_quantities=planned_quantities,
        item_by_id=item_by_id,
        items_by_order_item=_group(production_items, "customer_order_item_id"),
        movements_by_order_item=movements_by_order_item,
        orders_by_task=orders_by_task,
        batches_by_order=batches_by_order,
        repositories_by_order_item=repositories_by_order_item,
        reserved_by_repository=reserved_quantities(
            session, [item.id for item in repositories]
        ),
        bom_items=bom_items,
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


def _load_assembly_work_orders(
    session: Session,
    order_item_ids: set[int],
) -> tuple[dict[tuple[int, str], list[WorkOrder]], list[WorkOrder]]:
    grouped: dict[tuple[int, str], list[WorkOrder]] = defaultdict(list)
    work_orders = []
    for work_order, order_item_id in session.execute(
        select(WorkOrder, ProductionItem.customer_order_item_id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            ProductionItem.customer_order_item_id.in_(order_item_ids),
            WorkOrder.status != "cancelled",
        )
    ):
        work_orders.append(work_order)
        grouped[(order_item_id, work_order.flow_node_id)].append(work_order)
    return grouped, work_orders


def _load_batches_by_order(
    session: Session,
    work_order_ids: set[int],
) -> dict[int, list[WorkOrderBatch]]:
    result: dict[int, list[WorkOrderBatch]] = defaultdict(list)
    if work_order_ids:
        for batch in session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id.in_(work_order_ids)
            )
        ):
            result[batch.work_order_id].append(batch)
    return result


def _load_assembly_repositories(
    session: Session,
    production_item_ids: set[int],
    department_id: int,
) -> list[Repository]:
    if not production_item_ids:
        return []
    return list(
        session.scalars(
            select(Repository).where(
                Repository.production_item_id.in_(production_item_ids),
                Repository.department_id == department_id,
            )
        )
    )


def _assembly_task_row(
    task: _AssemblyTask,
    state: _AssemblyProgressState,
) -> dict:
    plan_item = task.plan_item
    order_item = task.order_item
    task_node_id = task.task_node["id"]
    output_unit_quantity = max(int(task.assembly_node.get("output_pcs") or 1), 1)
    task_quantity = (
        state.planned_quantities.get(order_item.id, 0) * output_unit_quantity
    )
    output_item = next(
        (
            item
            for item in state.items_by_order_item.get(order_item.id, [])
            if item.product_bom_id is None
            and item.origin_flow_node_id == plan_item.flow_node_id
        ),
        None,
    )
    task_orders = state.orders_by_task.get((order_item.id, task_node_id), [])
    task_repositories = [
        repository
        for repository in state.repositories_by_order_item.get(order_item.id, [])
        if repository.flow_node_id == task_node_id
        and repository.quantity
        - state.reserved_by_repository.get(repository.id, 0)
        > 0
    ]
    task_movements = state.movements_by_order_item.get(order_item.id, [])
    completed_quantity = released_task_quantity(
        task_movements, task_orders, task_node_id, task.nodes
    )
    arrived, material_arrivals, sources = _assembly_task_availability(
        task,
        state,
        task_quantity,
        output_item,
        task_repositories,
        task_movements,
    )
    workshop = state.workshops.get(task.task_node.get("workshop_id"))
    remarks = [
        value.strip()
        for value in (order_item.remark, task.order.remark)
        if value and value.strip()
    ]
    return {
        "production_plan_item_id": plan_item.id,
        "customer_order_item_id": plan_item.customer_order_item_id,
        "production_item_id": output_item.id if output_item else None,
        "flow_node_id": task_node_id,
        "plan_status": task.plan.status,
        "part_no": plan_item.item_code,
        "part_name": f"{task.product.product_name}-{plan_item.item_name}",
        "processing_workshop_id": workshop.id,
        "processing_workshop": (
            workshop.workshop_name
            if workshop
            else str(task.task_node.get("label") or "装配")
        ),
        "task_quantity": task_quantity,
        "arrived_quantity": arrived,
        "material_arrivals": material_arrivals,
        "processing_statuses": build_task_processing_statuses(
            task_orders,
            state.batches_by_order,
            available_sources=sources,
            task_quantity=task_quantity,
            completed_quantity=completed_quantity,
            assembly_output_unit_quantity=(
                output_unit_quantity
                if task_node_id == plan_item.flow_node_id
                else None
            ),
        ),
        "completed_quantity": completed_quantity,
        "remark": "；".join(dict.fromkeys(remarks)),
    }


def _assembly_task_availability(
    task: _AssemblyTask,
    state: _AssemblyProgressState,
    task_quantity: int,
    output_item: ProductionItem | None,
    task_repositories: list[Repository],
    task_movements: list[ProductionMovement],
) -> tuple[int, list[dict], list[TaskAvailableSource]]:
    task_node_id = task.task_node["id"]
    if task_node_id != task.plan_item.flow_node_id:
        arrived = sum(
            movement.quantity
            for movement in task_movements
            if movement.target_flow_node_id == task_node_id
            and movement.source_flow_node_id != task_node_id
        )
        sources = _repository_status_sources(
            [
                repository
                for repository in task_repositories
                if output_item is not None
                and repository.production_item_id == output_item.id
            ],
            state.processing_states,
            {task_node_id},
            state.reserved_by_repository,
        )
        return arrived, [], sources
    output_unit_quantity = max(int(task.assembly_node.get("output_pcs") or 1), 1)
    arrived, material_arrivals = assembly_arrival_progress(
        task.flow,
        task.nodes,
        task.plan_item.flow_node_id,
        output_unit_quantity,
        state.items_by_order_item.get(task.order_item.id, []),
        task_movements,
        state.bom_items,
        task_quantity,
    )
    initial_capacity = _initial_assembly_capacity(
        task_repositories,
        state.reserved_by_repository,
        state.item_by_id,
        task.flow,
        task.nodes,
        task_node_id,
        state.bom_items,
    )
    sources = []
    if initial_capacity > 0:
        sources.append(
            TaskAvailableSource(
                repository_id=None,
                processing_status="未加工 · 等待物料投入",
                has_current_position_processing=False,
                creation_mode="assembly_initial",
                quantity=initial_capacity,
            )
        )
    continuation_key = f"assembly:{task_node_id}"
    sources.extend(
        _repository_status_sources(
            [
                repository
                for repository in task_repositories
                if production_item_material_key(
                    state.item_by_id[repository.production_item_id]
                )
                == continuation_key
            ],
            state.processing_states,
            {task_node_id},
            state.reserved_by_repository,
        )
    )
    return arrived, material_arrivals, sources
def _repository_status_sources(
    repositories: list[Repository],
    processing_states: dict[int, MaterialProcessingState],
    task_node_ids: set[str],
    reserved_by_repository: dict[int, int],
) -> list[TaskAvailableSource]:
    result = []
    for repository in repositories:
        processing_state = processing_states[repository.processing_state_id]
        result.append(
            TaskAvailableSource(
                repository_id=repository.id,
                processing_status=processing_state.display_text,
                has_current_position_processing=any(
                    history.get("flow_node_id") in task_node_ids
                    for history in processing_state.procedure_history
                ),
                creation_mode="repository",
                quantity=max(
                    repository.quantity
                    - reserved_by_repository.get(repository.id, 0),
                    0,
                ),
            )
        )
    return result


def _initial_assembly_capacity(
    repositories: list[Repository],
    reserved_by_repository: dict[int, int],
    production_item_by_id: dict[int, ProductionItem],
    flow: dict,
    nodes: dict[str, dict],
    assembly_node_id: str,
    bom_items: dict[int, ProductBom],
) -> int:
    required = set(
        normal_input_material_keys(
            flow,
            nodes,
            assembly_node_id,
        )
    )
    if not required:
        return 0
    available_by_key: dict[str, int] = defaultdict(int)
    unit_by_key: dict[str, int] = {}
    for repository in repositories:
        item = production_item_by_id.get(repository.production_item_id)
        if item is None:
            continue
        key = production_item_material_key(item)
        if key not in required:
            continue
        available_by_key[key] += max(
            repository.quantity - reserved_by_repository.get(repository.id, 0),
            0,
        )
        if item.product_bom_id is not None:
            bom_item = bom_items.get(item.product_bom_id)
            unit_by_key[key] = max(int(bom_item.pcs if bom_item else 1), 1)
        else:
            origin = nodes.get(item.origin_flow_node_id, {})
            unit_by_key[key] = max(int(origin.get("output_pcs") or 1), 1)
    if not required.issubset(available_by_key):
        return 0
    return min(
        available_by_key[key] // unit_by_key.get(key, 1)
        for key in required
    )
