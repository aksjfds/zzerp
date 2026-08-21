from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from database import SessionLocal
from domain.time import business_iso
from modules.engineering.model_api import Product, ProductBom
from modules.errors import DomainError
from modules.organization.model_api import Department, Procedure, Workshop
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.assembly_progress import assembly_arrived_output_quantity
from modules.production_core.model_api import (
    ProductionItem,
    ProductionMovement,
    WorkOrder,
)
from modules.production_core.operational_api import (
    calculate_assembly_output_progress,
    calculate_work_order_progress,
    load_product_flow,
)
from modules.production_core.flow import physical_route_nodes
from modules.quality.model_api import WorkOrderBatch
from modules.sales.model_api import CustomerOrder, CustomerOrderItem
from modules.workforce.model_api import Worker


ARRIVAL_MOVEMENT_TYPES = {
    "initial",
    "inventory_issue",
    "process",
    "purchase_receipt",
    "assembly_output",
}
QC_FORWARD_MOVEMENT_TYPES = {"qc_qualified"}


def get_department_production_progress_item(
    department_code: str,
    production_plan_item_id: int,
    processing_workshop: str | None = None,
    flow_node_id: str | None = None,
) -> dict:
    with SessionLocal() as session:
        plan_item = session.get(ProductionPlanItem, production_plan_item_id)
        if plan_item is None:
            raise DomainError(
                "production_plan_item_not_found",
                "生产计划明细不存在",
                status_code=404,
            )
        plan = session.get(ProductionPlan, plan_item.production_plan_id)
        order_item = session.get(CustomerOrderItem, plan_item.customer_order_item_id)
        order = session.get(CustomerOrder, plan.customer_order_id) if plan else None
        product = session.get(Product, plan_item.product_id)
        if plan is None or order_item is None or order is None or product is None:
            raise DomainError(
                "production_progress_context_missing",
                "生产计划关联数据不完整",
                status_code=409,
            )

        flow, nodes = load_product_flow(
            session,
            plan_item.product_id,
            plan_item.product_version,
        )
        route_nodes = _physical_route_nodes(flow, nodes, plan_item.flow_node_id)
        procedures = {
            item.id: item for item in session.scalars(select(Procedure)).all()
        }
        workshops = {
            item.id: item for item in session.scalars(select(Workshop)).all()
        }
        departments = {
            item.id: item for item in session.scalars(select(Department)).all()
        }
        department_codes = {
            item.department_code: item for item in departments.values()
        }
        department_route_nodes = [
            node
            for node in route_nodes
            if _node_department_code(
                node,
                workshops,
                departments,
            ) == department_code
        ]
        if not department_route_nodes:
            raise DomainError(
                "production_progress_item_access_denied",
                "该生产任务不属于当前部门",
                status_code=403,
            )
        if flow_node_id:
            department_route_nodes = [
                node for node in department_route_nodes
                if node["id"] == flow_node_id
            ]
            if not department_route_nodes:
                raise DomainError(
                    "production_progress_node_not_found",
                    "当前生产任务节点不存在，请刷新后重试",
                    status_code=404,
                )
        if processing_workshop:
            department_route_nodes = [
                node
                for node in department_route_nodes
                if _node_workshop_name(
                    node,
                    workshops,
                ) == processing_workshop
            ]
            if not department_route_nodes:
                raise DomainError(
                    "production_progress_workshop_not_found",
                    "当前加工工艺不存在，请刷新后重试",
                    status_code=404,
                )

        route_node_ids = {node["id"] for node in route_nodes}
        order_production_items = list(session.scalars(
            select(ProductionItem).where(
                ProductionItem.customer_order_item_id
                == plan_item.customer_order_item_id,
                ProductionItem.product_id == plan_item.product_id,
                ProductionItem.product_version == plan_item.product_version,
            )
        ).all())
        production_items = [
            item for item in order_production_items
            if item.origin_flow_node_id == plan_item.flow_node_id
            and (
                item.product_bom_id is None
                if plan_item.product_bom_id is None
                else item.product_bom_id == plan_item.product_bom_id
            )
        ]
        production_item_ids = {item.id for item in production_items}

        work_orders = list(session.scalars(
            select(WorkOrder)
            .join(
                ProductionItem,
                ProductionItem.id == WorkOrder.production_item_id,
            )
            .where(
                ProductionItem.customer_order_item_id
                == plan_item.customer_order_item_id,
                WorkOrder.flow_node_id.in_(route_node_ids),
            )
            .order_by(WorkOrder.id.desc())
        ).all()) if route_node_ids else []
        work_order_ids = {item.id for item in work_orders}
        work_order_by_id = {item.id: item for item in work_orders}
        batches = list(session.scalars(
            select(WorkOrderBatch).where(
                WorkOrderBatch.work_order_id.in_(work_order_ids)
            )
        ).all()) if work_order_ids else []
        batches_by_order: dict[int, list[WorkOrderBatch]] = defaultdict(list)
        for batch in batches:
            batches_by_order[batch.work_order_id].append(batch)

        worker_ids = {item.worker_id for item in work_orders if item.worker_id}
        workers = {
            item.id: item
            for item in session.scalars(
                select(Worker).where(Worker.id.in_(worker_ids))
            ).all()
        } if worker_ids else {}

        movement_items = (
            order_production_items
            if plan_item.item_type == "assembly"
            else production_items
        )
        movement_item_ids = {item.id for item in movement_items}
        movements = list(session.scalars(
            select(ProductionMovement).where(
                ProductionMovement.production_item_id.in_(movement_item_ids)
            )
        ).all()) if movement_item_ids else []
        arrivals_by_node: dict[str, int] = defaultdict(int)
        if plan_item.item_type == "assembly":
            assembly_node = nodes.get(plan_item.flow_node_id, {})
            bom_items = {
                item.id: item
                for item in session.scalars(
                    select(ProductBom).where(
                        ProductBom.product_id == plan_item.product_id
                    )
                )
            }
            arrivals_by_node[plan_item.flow_node_id] = (
                assembly_arrived_output_quantity(
                    flow,
                    nodes,
                    plan_item.flow_node_id,
                    int(assembly_node.get("output_pcs") or 1),
                    order_production_items,
                    movements,
                    bom_items,
                )
            )
            for node_id in route_node_ids - {plan_item.flow_node_id}:
                arrivals_by_node[node_id] = sum(
                    movement.quantity
                    for movement in movements
                    if movement.target_flow_node_id == node_id
                    and movement.source_flow_node_id != node_id
                )
        else:
            for movement in movements:
                movement_order = work_order_by_id.get(movement.work_order_id)
                is_qc_forward = (
                    movement.movement_type in QC_FORWARD_MOVEMENT_TYPES
                    and movement_order is not None
                    and movement.target_flow_node_id != movement_order.flow_node_id
                )
                if (
                    (
                        movement.movement_type in ARRIVAL_MOVEMENT_TYPES
                        or is_qc_forward
                    )
                    and movement.target_flow_node_id in route_node_ids
                    and movement.source_flow_node_id != movement.target_flow_node_id
                ):
                    arrivals_by_node[movement.target_flow_node_id] += movement.quantity

        cards = []
        for sort_order, node in enumerate(department_route_nodes, start=1):
            workshop = workshops.get(node.get("workshop_id"))
            department = departments.get(workshop.department_id) if workshop else None
            node_type = node.get("type")
            if node_type == "assembly":
                department = department or department_codes.get("assembly")
            if node_type not in {"process", "assembly"} or department is None:
                continue
            node_orders = [
                item for item in work_orders
                if item.flow_node_id == node["id"] and item.status != "cancelled"
            ]
            procedure_ids = list(dict.fromkeys(
                item.procedure_id for item in node_orders if item.procedure_id is not None
            )) or [None]
            for procedure_id in procedure_ids:
                procedure = procedures.get(procedure_id) if procedure_id else None
                cards.append(_card(
                    node=node,
                    procedure=procedure,
                    workshop=workshop,
                    department=department,
                    orders=[
                        item for item in node_orders
                        if item.procedure_id == procedure_id
                    ],
                    batches_by_order=batches_by_order,
                    workers=workers,
                    task_quantity=plan_item.planned_production_quantity,
                    arrived_quantity=arrivals_by_node.get(node["id"], 0),
                    sort_order=sort_order,
                ))

        return {
            "production_plan_item_id": plan_item.id,
            "production_item_ids": sorted(production_item_ids),
            "customer_order_no": order.customer_order_no,
            "factory_code": product.factory_code,
            "product_name": product.product_name,
            "part_no": plan_item.item_code,
            "part_name": plan_item.item_name,
            "plan_status": plan.status,
            "task_quantity": plan_item.planned_production_quantity,
            "cards": cards,
        }


def _card(
    *,
    node,
    procedure,
    workshop,
    department,
    orders,
    batches_by_order,
    workers,
    task_quantity,
    arrived_quantity,
    sort_order,
) -> dict:
    order_rows = []
    processing_quantity = 0
    ready_for_qc_quantity = 0
    pending_qc_quantity = 0
    completed_quantity = 0
    rework_quantity = 0
    scrap_quantity = 0
    lost_quantity = 0
    output_unit_quantity = (
        max(int(node.get("output_pcs") or 1), 1)
        if node.get("type") == "assembly" else 1
    )
    for order in orders:
        batches = batches_by_order.get(order.id, [])
        progress = (
            calculate_assembly_output_progress(
                order,
                batches,
                output_unit_quantity,
            )
            if node.get("type") == "assembly"
            else calculate_work_order_progress(order, batches)
        )
        processing_quantity += progress.processing_quantity
        ready_for_qc_quantity += progress.ready_for_qc_quantity
        pending_qc_quantity += progress.pending_qc_quantity
        completed_quantity += progress.qualified_quantity
        rework_quantity += progress.rework_quantity
        scrap_quantity += progress.scrap_quantity
        lost_quantity += progress.lost_quantity
        worker = workers.get(order.worker_id)
        order_rows.append({
            "id": order.id,
            "work_order_no": order.work_order_no,
            "worker_name": worker.worker_name if worker else None,
            "quantity": order.quantity * output_unit_quantity,
            "processed_quantity": progress.processed_quantity,
            "submitted_quantity": progress.submitted_quantity,
            "pending_qc_quantity": progress.pending_qc_quantity,
            "completed_quantity": progress.qualified_quantity,
            "rework_quantity": progress.rework_quantity,
            "scrap_quantity": progress.scrap_quantity,
            "lost_quantity": progress.lost_quantity,
            "status": order.status,
            "created_at": business_iso(order.created_at),
            "closed_at": business_iso(order.closed_at),
        })
    status = _card_status(
        task_quantity,
        arrived_quantity,
        processing_quantity,
        ready_for_qc_quantity,
        pending_qc_quantity,
        completed_quantity,
        rework_quantity,
        scrap_quantity,
        lost_quantity,
    )
    card_type = (
        "assembly" if node.get("type") == "assembly"
        else "purchase" if procedure and procedure.procedure_type == "purchase_receipt"
        else "process"
    )
    card_name = procedure.procedure_name if procedure else "尚未开工单"
    return {
        "card_key": f"{card_type}:{node['id']}:{procedure.id if procedure else 'empty'}",
        "card_type": card_type,
        "sort_order": sort_order,
        "flow_node_id": node["id"],
        "procedure_id": procedure.id if procedure else None,
        "card_name": card_name,
        "department_code": department.department_code,
        "department_name": department.department_name,
        "workshop_name": workshop.workshop_name if workshop else department.department_name,
        "procedure_name": procedure.procedure_name if procedure else node.get("label", "装配"),
        "status": status,
        "task_quantity": task_quantity,
        "arrived_quantity": arrived_quantity,
        "processing_quantity": processing_quantity,
        "ready_for_qc_quantity": ready_for_qc_quantity,
        "pending_qc_quantity": pending_qc_quantity,
        "completed_quantity": completed_quantity,
        "rework_quantity": rework_quantity,
        "scrap_quantity": scrap_quantity,
        "lost_quantity": lost_quantity,
        "work_orders": order_rows,
    }


def _card_status(
    task_quantity,
    arrived_quantity,
    processing_quantity,
    ready_for_qc_quantity,
    pending_qc_quantity,
    completed_quantity,
    rework_quantity,
    scrap_quantity,
    lost_quantity,
) -> str:
    if rework_quantity or scrap_quantity or lost_quantity:
        return "exception"
    if completed_quantity >= task_quantity and task_quantity > 0:
        return "completed"
    if ready_for_qc_quantity or pending_qc_quantity:
        return "pending_qc"
    if processing_quantity:
        return "processing"
    if arrived_quantity:
        return "ready"
    return "not_arrived"


def _physical_route_nodes(flow, nodes, origin_node_id):
    origin = nodes.get(origin_node_id)
    if origin and origin.get("type") == "assembly":
        return physical_route_nodes(flow, nodes, origin_node_id)
    route = []
    current = _normal_target(flow, nodes, origin_node_id)
    visited = set()
    while current and current["id"] not in visited:
        visited.add(current["id"])
        route.append(current)
        if current.get("type") in {"assembly", "shipping"}:
            break
        current = _normal_target(flow, nodes, current["id"])
    return route


def _normal_target(flow, nodes, node_id):
    targets = [
        nodes.get(edge.get("target_node_id"))
        for edge in flow.get("edges", [])
        if edge.get("source_node_id") == node_id
    ]
    targets = [item for item in targets if item is not None]
    return targets[0] if len(targets) == 1 else None


def _node_department_code(node, workshops, departments):
    if node.get("type") in {"process", "assembly"}:
        workshop = workshops.get(node.get("workshop_id"))
        department = departments.get(workshop.department_id) if workshop else None
        return department.department_code if department else None
    return {
        "qc": "qc",
        "shipping": "finished",
    }.get(node.get("type"))


def _node_workshop_name(node, workshops):
    workshop = workshops.get(node.get("workshop_id"))
    if workshop:
        return workshop.workshop_name
    if node.get("type") == "assembly":
        return str(node.get("label") or "装配")
    return None


__all__ = ["get_department_production_progress_item"]
