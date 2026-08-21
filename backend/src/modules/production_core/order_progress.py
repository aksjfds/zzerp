from __future__ import annotations

from collections import defaultdict
from math import ceil

from sqlalchemy import select

from modules.organization.model_api import Department, Workshop
from modules.production_core.persistence import (
    ProductionItem,
    ProductionMovement,
    Repository,
    WorkOrder,
)
from modules.sales.model_api import CustomerOrderItem
from modules.errors import DomainError
from modules.production_core.operational_api import load_product_flow
from modules.production_core.operational_api import order_remaining_quantity
from modules.production_core.operational_api import terminal_unit_quantity


def order_item_progress(
    session,
    order_item: CustomerOrderItem,
    *,
    order_status: str,
) -> dict:
    total = order_item.quantity
    try:
        flow, nodes = load_product_flow(
            session,
            order_item.product_id,
            order_item.product_version,
        )
    except DomainError:
        return _empty_progress(order_item)
    production_items = list(session.scalars(
        select(ProductionItem).where(
            ProductionItem.customer_order_item_id == order_item.id
        )
    ).all())
    production_item_ids = [item.id for item in production_items]
    movements = list(session.scalars(
        select(ProductionMovement).where(
            ProductionMovement.production_item_id.in_(production_item_ids)
        )
    ).all()) if production_item_ids else []

    completed = _completed_quantity(session, total, flow, nodes, movements)
    scrap, lost = _abnormal_quantities(session, flow, nodes, movements)
    remaining_after_completed = max(total - completed, 0)
    scrap = min(scrap, remaining_after_completed)
    lost = min(lost, remaining_after_completed - scrap)
    unfinished = max(total - completed - scrap - lost, 0)
    po_shortage = min(
        _po_shortage_quantity(
            session,
            flow,
            nodes,
            production_item_ids,
            draft_quantity=total if order_status == "draft" else 0,
        ),
        unfinished,
    )
    return {
        "customer_order_item_id": order_item.id,
        "product_id": order_item.product_id,
        "product_name": "",
        "factory_code": "",
        "total_quantity": total,
        "completed_quantity": completed,
        "scrap_quantity": scrap,
        "lost_quantity": lost,
        "unfinished_quantity": unfinished,
        "po_shortage_quantity": po_shortage,
    }


def _empty_progress(order_item: CustomerOrderItem) -> dict:
    return {
        "customer_order_item_id": order_item.id,
        "product_id": order_item.product_id,
        "product_name": "",
        "factory_code": "",
        "total_quantity": order_item.quantity,
        "completed_quantity": 0,
        "scrap_quantity": 0,
        "lost_quantity": 0,
        "unfinished_quantity": order_item.quantity,
        "po_shortage_quantity": 0,
    }


def _completed_quantity(session, total: int, flow: dict, nodes: dict, movements: list) -> int:
    shipping_nodes = [node for node in nodes.values() if node.get("type") == "shipping"]
    if len(shipping_nodes) != 1:
        return 0
    shipping_node = shipping_nodes[0]
    unit_quantity = terminal_unit_quantity(session, flow, nodes, shipping_node["id"])
    if not unit_quantity:
        return 0
    shipped = sum(
        movement.quantity
        for movement in movements
        if movement.movement_type == "customer_shipment"
        and movement.target_flow_node_id == shipping_node["id"]
    )
    return min(shipped // unit_quantity, total)


def _abnormal_quantities(session, flow: dict, nodes: dict, movements: list) -> tuple[int, int]:
    quantities: dict[tuple[int, int, str], int] = defaultdict(int)
    for movement in movements:
        if movement.movement_type not in {"scrap", "lost"}:
            continue
        unit_quantity = terminal_unit_quantity(
            session,
            flow,
            nodes,
            movement.source_flow_node_id,
        )
        if not unit_quantity:
            continue
        quantities[(movement.production_item_id, unit_quantity, movement.movement_type)] += (
            movement.quantity
        )

    by_item: dict[int, dict[str, int]] = defaultdict(lambda: {"scrap": 0, "lost": 0})
    for (production_item_id, unit_quantity, movement_type), quantity in quantities.items():
        by_item[production_item_id][movement_type] += ceil(quantity / unit_quantity)
    if not by_item:
        return 0, 0
    bottleneck = max(
        by_item.values(),
        key=lambda item: (item["scrap"] + item["lost"], item["scrap"], item["lost"]),
    )
    return bottleneck["scrap"], bottleneck["lost"]


def _po_shortage_quantity(
    session,
    flow: dict,
    nodes: dict,
    production_item_ids: list[int],
    *,
    draft_quantity: int,
) -> int:
    process_nodes = [node for node in nodes.values() if node.get("type") == "process"]
    purchase_workshop_ids = set(session.scalars(
        select(Workshop.id)
        .join(Department, Department.id == Workshop.department_id)
        .where(Department.department_code == "purchasing")
    ).all())
    purchase_node_ids = {
        node["id"]
        for node in process_nodes
        if node.get("workshop_id") in purchase_workshop_ids
    }
    if not purchase_node_ids:
        return 0
    if not production_item_ids:
        return draft_quantity

    repositories = list(session.scalars(
        select(Repository).where(
            Repository.production_item_id.in_(production_item_ids),
            Repository.flow_node_id.in_(purchase_node_ids),
        )
    ).all())
    if not repositories:
        return 0
    open_orders = list(session.scalars(
        select(WorkOrder).where(
            WorkOrder.repository_id.in_([item.id for item in repositories]),
            WorkOrder.work_order_type == "purchase_receipt",
            WorkOrder.status == "open",
        )
    ).all())
    reserved_by_repository: dict[int, int] = defaultdict(int)
    for order in open_orders:
        if order.repository_id is not None:
            reserved_by_repository[order.repository_id] += order_remaining_quantity(order)

    shortages = []
    for repository in repositories:
        uncovered = max(
            repository.quantity - reserved_by_repository.get(repository.id, 0),
            0,
        )
        unit_quantity = terminal_unit_quantity(
            session,
            flow,
            nodes,
            repository.flow_node_id,
        )
        if unit_quantity:
            shortages.append(ceil(uncovered / unit_quantity))
    return max(shortages, default=0)
