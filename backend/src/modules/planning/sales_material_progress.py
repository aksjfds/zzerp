"""Batch-loaded material-position projection for sales progress details."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from modules.organization.read_api import (
    get_department_views_by_ids,
    get_workshop_views,
)
from modules.planning.order_production_context import (
    _load_order_production_context,
)
from modules.planning.persistence import (
    ProductionPlan,
    ProductionPlanItem,
    ProductionRouteTask,
)
from modules.planning.plan_builder import planned_product_quantity
from modules.planning.production_progress_arrivals import (
    calculate_progress_arrivals,
)
from modules.planning.progress_calculations import released_task_quantity
from modules.planning.task_status_summary import (
    TaskAvailableSource,
    build_task_processing_statuses,
)
from modules.production_core.flow_api import load_product_flow
from modules.production_core.model_api import MaterialProcessingState
from modules.production_core.workbench_read_api import reserved_quantities
from modules.sales.model_api import CustomerOrderItem


def order_progress_by_order_item(
    session,
    customer_order_item_ids: list[int],
) -> dict[int, dict]:
    """Return product task totals and ordered material positions for one page."""
    if not customer_order_item_ids:
        return {}
    order_items = list(session.scalars(
        select(CustomerOrderItem).where(
            CustomerOrderItem.id.in_(customer_order_item_ids)
        )
    ))
    if not order_items:
        return {}
    plan_rows = list(session.execute(
        select(ProductionPlanItem, ProductionPlan)
        .join(
            ProductionPlan,
            ProductionPlan.id == ProductionPlanItem.production_plan_id,
        )
        .where(
            ProductionPlanItem.customer_order_item_id.in_(customer_order_item_ids),
        )
        .order_by(
            ProductionPlanItem.customer_order_item_id,
            ProductionPlanItem.sort_order,
            ProductionPlanItem.id,
        )
    ))
    if not plan_rows:
        return {}

    all_plan_items = [row[0] for row in plan_rows]
    plan_items = [
        item for item in all_plan_items if item.item_type in {"part", "assembly"}
    ]
    plan_status_by_item_id = {row[0].id: row[1].status for row in plan_rows}
    route_tasks = list(session.scalars(
        select(ProductionRouteTask)
        .where(
            ProductionRouteTask.production_plan_item_id.in_(
                [item.id for item in plan_items]
            )
        )
        .order_by(
            ProductionRouteTask.production_plan_item_id,
            ProductionRouteTask.route_order,
            ProductionRouteTask.id,
        )
    ))
    routes_by_plan_item: dict[int, list[ProductionRouteTask]] = defaultdict(list)
    for route_task in route_tasks:
        routes_by_plan_item[route_task.production_plan_item_id].append(route_task)

    context = _load_order_production_context(session, order_items)
    repository_ids = [
        repository.id
        for repositories in context.repositories_by_item.values()
        for repository in repositories
    ]
    reserved_by_repository = reserved_quantities(session, repository_ids)
    processing_state_ids = {
        repository.processing_state_id
        for repositories in context.repositories_by_item.values()
        for repository in repositories
    }
    processing_states = {
        state.id: state
        for state in session.scalars(
            select(MaterialProcessingState).where(
                MaterialProcessingState.id.in_(processing_state_ids)
            )
        )
    } if processing_state_ids else {}
    work_order_by_id = {
        work_order.id: work_order
        for work_orders in context.work_orders_by_item.values()
        for work_order in work_orders
    }
    workshops = {
        item.id: item
        for item in get_workshop_views(
            session,
            workshop_ids={
                task.workshop_id
                for task in route_tasks
                if task.workshop_id is not None
            },
        )
    }
    departments = {
        item.id: item
        for item in get_department_views_by_ids(
            session,
            {task.department_id for task in route_tasks},
        )
    }
    production_item_by_identity = {
        (
            production_item.customer_order_item_id,
            production_item.product_id,
            production_item.product_version,
            production_item.product_bom_id,
            production_item.origin_flow_node_id,
        ): production_item
        for production_items in context.production_items_by_order_item.values()
        for production_item in production_items
    }

    all_plan_items_by_order_item: dict[int, list[ProductionPlanItem]] = defaultdict(list)
    for item in all_plan_items:
        all_plan_items_by_order_item[item.customer_order_item_id].append(item)
    result: dict[int, dict] = {
        order_item_id: {
            "task_quantity": planned_product_quantity(items),
            "materials": [],
        }
        for order_item_id, items in all_plan_items_by_order_item.items()
    }
    order_item_by_id = {item.id: item for item in order_items}
    for plan_item in plan_items:
        order_item = order_item_by_id.get(plan_item.customer_order_item_id)
        if order_item is None:
            continue
        production_item = production_item_by_identity.get(_plan_item_identity(plan_item))
        flow, nodes = load_product_flow(
            session,
            plan_item.product_id,
            plan_item.product_version,
            context.display.flow_cache,
        )
        order_production_items = context.production_items_by_order_item.get(
            order_item.id,
            [],
        )
        order_movements = [
            movement
            for item in order_production_items
            for movement in context.movements_by_item.get(item.id, [])
        ]
        route = routes_by_plan_item.get(plan_item.id, [])
        route_node_ids = {task.route_flow_node_id for task in route}
        arrivals_by_node = calculate_progress_arrivals(
            plan_item=plan_item,
            flow=flow,
            nodes=nodes,
            route_node_ids=route_node_ids,
            order_production_items=order_production_items,
            movements=order_movements,
            work_order_by_id=work_order_by_id,
            bom_items=context.bom_items,
        )
        positions = _material_positions(
            plan_item=plan_item,
            plan_status=plan_status_by_item_id[plan_item.id],
            production_item=production_item,
            route=route,
            nodes=nodes,
            context=context,
            arrivals_by_node=arrivals_by_node,
            reserved_by_repository=reserved_by_repository,
            processing_states=processing_states,
            workshops=workshops,
            departments=departments,
        )
        result[plan_item.customer_order_item_id]["materials"].append({
            "production_plan_item_id": plan_item.id,
            "item_type": plan_item.item_type,
            "item_code": plan_item.item_code,
            "item_name": plan_item.item_name,
            "task_quantity": plan_item.planned_production_quantity,
            "positions": positions,
        })
    return dict(result)


def _material_positions(
    *,
    plan_item,
    plan_status: str,
    production_item,
    route,
    nodes,
    context,
    arrivals_by_node,
    reserved_by_repository,
    processing_states,
    workshops,
    departments,
) -> list[dict]:
    if not route:
        return []
    if plan_status in {"draft", "cancelled"}:
        return [_position_row(
            route[0],
            status=("plan_unconfirmed" if plan_status == "draft" else "plan_cancelled"),
            label=("计划未确认" if plan_status == "draft" else "计划已取消"),
            quantity=plan_item.planned_production_quantity,
            procedure_names=[],
            position_name="—",
            department_name="—",
        )]
    movements = (
        context.movements_by_item.get(production_item.id, [])
        if production_item is not None
        else []
    )
    work_orders = (
        [
            order
            for order in context.work_orders_by_item.get(production_item.id, [])
            if order.status != "cancelled"
        ]
        if production_item is not None
        else []
    )
    repositories = (
        context.repositories_by_item.get(production_item.id, [])
        if production_item is not None
        else []
    )
    positions = []
    for task in route:
        node_id = task.route_flow_node_id
        node_orders = [order for order in work_orders if order.flow_node_id == node_id]
        node_repositories = [
            repository
            for repository in repositories
            if repository.flow_node_id == node_id
        ]
        available_sources = _available_sources(
            node_repositories,
            reserved_by_repository,
            processing_states,
            node_id,
        )
        transferred_quantity = released_task_quantity(
            movements,
            node_orders,
            node_id,
            nodes,
        )
        calculated_status_rows = (
            build_task_processing_statuses(
                node_orders,
                context.batches_by_order,
                available_sources=available_sources,
                task_quantity=plan_item.planned_production_quantity,
                completed_quantity=transferred_quantity,
                assembly_output_unit_quantity=(
                    max(int(nodes.get(node_id, {}).get("output_pcs") or 1), 1)
                    if task.route_node_type == "assembly"
                    and node_id == plan_item.flow_node_id
                    else None
                ),
            )
            if available_sources or node_orders
            else []
        )
        status_rows = [
            status
            for status in calculated_status_rows
            if status["status"] != "department_completed"
            and not (
                status["status"] == "not_started"
                and status["action"] == "none"
            )
        ]
        node = nodes.get(node_id, {})
        workshop = workshops.get(task.workshop_id)
        department = departments.get(task.department_id)
        position_name = (
            workshop.workshop_name
            if workshop is not None
            else str(node.get("label") or "委外加工")
        )
        department_name = department.department_name if department is not None else "—"
        for status in status_rows:
            status_label = status["label"]
            if (
                task.route_node_type == "assembly"
                and plan_item.item_type == "part"
                and status["status"] == "not_started"
            ):
                status_label = "等待装配"
            status_position_name = position_name
            if task.route_node_type == "supplier_processing":
                related_order_ids = {
                    item["work_order_id"] for item in status["related_work_orders"]
                }
                supplier_names = sorted({
                    order.supplier_name
                    for order in node_orders
                    if order.id in related_order_ids and order.supplier_name
                })
                if supplier_names:
                    status_position_name = "、".join(supplier_names)
            positions.append(_position_row(
                task,
                status=status["status"],
                label=status_label,
                quantity=status["quantity"],
                procedure_names=status["procedure_names"],
                position_name=(
                    "QC"
                    if status["status"] == "submitted_qc"
                    else status_position_name
                ),
                department_name=("QC" if status["status"] == "submitted_qc" else department_name),
            ))
        consumed_quantity = _assembly_consumed_quantity(movements, node_id)
        if consumed_quantity > 0:
            positions.append(_position_row(
                task,
                status="assembly_consumed",
                label="已投入装配",
                quantity=consumed_quantity,
                procedure_names=[],
                position_name=position_name,
                department_name=department_name,
            ))
        stored_quantity = _stored_quantity(movements, node_id)
        if stored_quantity > 0:
            positions.append(_position_row(
                task,
                status="stored",
                label="已入仓",
                quantity=stored_quantity,
                procedure_names=[],
                position_name="仓库",
                department_name="仓库",
            ))
        if transferred_quantity > 0:
            positions.append(_position_row(
                task,
                status="transferred",
                label="已流转",
                quantity=transferred_quantity,
                procedure_names=[],
                position_name=position_name,
                department_name=department_name,
            ))
        if (
            not status_rows
            and consumed_quantity <= 0
            and stored_quantity <= 0
            and transferred_quantity <= 0
        ):
            arrived_quantity = int(arrivals_by_node.get(node_id, 0))
            if arrived_quantity > 0:
                status, label, quantity = "not_started", "等待开工", arrived_quantity
            else:
                status, label, quantity = "not_arrived", "未到达", 0
            positions.append(_position_row(
                task,
                status=status,
                label=label,
                quantity=quantity,
                procedure_names=[],
                position_name=position_name,
                department_name=department_name,
            ))
    return positions


def _available_sources(
    repositories,
    reserved_by_repository,
    processing_states,
    node_id: str,
) -> list[TaskAvailableSource]:
    sources = []
    for repository in repositories:
        quantity = repository.quantity - reserved_by_repository.get(repository.id, 0)
        if quantity <= 0:
            continue
        processing_state = processing_states[repository.processing_state_id]
        sources.append(TaskAvailableSource(
            repository_id=repository.id,
            processing_status=processing_state.display_text,
            has_current_position_processing=any(
                history.get("flow_node_id") == node_id
                for history in processing_state.procedure_history
            ),
            creation_mode="repository",
            quantity=quantity,
        ))
    return sources


def _assembly_consumed_quantity(movements, node_id: str) -> int:
    consumed = sum(
        movement.quantity
        for movement in movements
        if movement.movement_type == "assembly_input"
        and movement.source_flow_node_id == node_id
    )
    restored = sum(
        movement.quantity
        for movement in movements
        if movement.movement_type == "assembly_input_restore"
        and movement.target_flow_node_id == node_id
    )
    return max(consumed - restored, 0)


def _stored_quantity(movements, node_id: str) -> int:
    stored = sum(
        movement.quantity
        for movement in movements
        if movement.movement_type == "production_inventory"
        and movement.source_flow_node_id == node_id
    )
    restored = sum(
        movement.quantity
        for movement in movements
        if movement.movement_type == "production_inventory_restore"
        and movement.target_flow_node_id == node_id
    )
    return max(stored - restored, 0)


def _position_row(
    task,
    *,
    status: str,
    label: str,
    quantity: int,
    procedure_names: list[str],
    position_name: str,
    department_name: str,
) -> dict:
    return {
        "flow_node_id": task.route_flow_node_id,
        "route_order": task.route_order,
        "position_name": position_name.removesuffix("车间") or position_name,
        "department_name": department_name,
        "status": status,
        "status_label": label,
        "quantity": quantity,
        "procedure_names": procedure_names,
    }


def _plan_item_identity(plan_item) -> tuple:
    return (
        plan_item.customer_order_item_id,
        plan_item.product_id,
        plan_item.product_version,
        plan_item.product_bom_id,
        plan_item.flow_node_id,
    )


__all__ = ["order_progress_by_order_item"]
