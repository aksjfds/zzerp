from __future__ import annotations

"""Production-plan inventory display and decomposition."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.warehouse import WAREHOUSE_CODE_MAIN, WAREHOUSE_NAME_MAIN
from modules.engineering.model_api import ProductBom
from modules.inventory.plan_stock_api import finished_plan_reservation_quantities
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.plan_stock_view import (
    completion_status_priority,
    load_plan_item_stocks,
)
from modules.production_core.flow_api import load_product_flow


def _serialize_inventory_items(session: Session, plan: ProductionPlan) -> list[dict]:
    flow_cache: dict = {}
    stock_groups = load_plan_item_stocks(session, plan.items, flow_cache)
    reservation_quantities = finished_plan_reservation_quantities(session, plan.id)
    bom_ids = {
        item.product_bom_id
        for item in plan.items
        if item.product_bom_id is not None
    }
    bom_by_id = {
        item.id: item
        for item in session.scalars(select(ProductBom).where(ProductBom.id.in_(bom_ids)))
    } if bom_ids else {}
    requirements = {
        item.product_bom_id: item.unit_requirement
        for item in plan.items
        if item.item_type == "part" and item.product_bom_id is not None
    }
    incoming_by_product: dict[tuple[int, int], dict[str, list[str]]] = {}
    reachable_bom_cache: dict[tuple[int, int, str], set[int]] = {}
    rows: list[dict] = []
    for item in plan.items:
        _flow, nodes = load_product_flow(
            session,
            item.product_id,
            item.product_version,
            flow_cache,
        )
        product_key = (item.product_id, item.product_version)
        if product_key not in incoming_by_product:
            incoming: dict[str, list[str]] = {}
            for edge in _flow.get("edges", []):
                source_id = edge.get("source_node_id")
                target_id = edge.get("target_node_id")
                if source_id and target_id:
                    incoming.setdefault(target_id, []).append(source_id)
            incoming_by_product[product_key] = incoming
        stocks = list(stock_groups.get(item.identity_key, ()))
        if item.item_type in {"part", "assembly"}:
            priority = {
                status: index
                for index, status in enumerate(
                    completion_status_priority(session, item, flow_cache)
                )
            }
            stocks.sort(key=lambda stock: (
                priority.get(stock.completion_status, len(priority)),
                stock.stock_id,
            ))
        else:
            stocks.sort(key=lambda stock: stock.stock_id)
        item_name = item.item_name
        if item.item_type == "part" and item.product_bom_id is not None:
            bom_item = bom_by_id.get(item.product_bom_id)
            if bom_item is not None:
                item_name = bom_item.part_name
        if not stocks:
            warehouse_code, warehouse_name = _default_warehouse(item.item_type)
            rows.append(_inventory_item_row(
                item,
                None,
                "—",
                warehouse_code,
                warehouse_name,
                0,
                0,
                0,
                0,
                item_name,
                _inventory_decomposition(
                    item,
                    0,
                    nodes,
                    incoming_by_product[product_key],
                    requirements,
                    bom_by_id,
                    reachable_bom_cache,
                ),
            ))
            continue
        remaining_allocation = item.estimated_inventory_quantity
        for stock in stocks:
            if plan.status == "draft":
                allocation = min(remaining_allocation, stock.available_quantity)
                remaining_allocation -= allocation
            elif item.item_type == "finished_product":
                allocation = reservation_quantities.get((item.id, stock.stock_id), 0)
            else:
                allocation = 0
            rows.append(_inventory_item_row(
                item,
                stock.stock_id,
                stock.completion_status,
                stock.warehouse_code,
                stock.warehouse_name,
                stock.stock_quantity,
                stock.reserved_quantity,
                stock.available_quantity,
                allocation,
                item_name,
                _inventory_decomposition(
                    item,
                    stock.available_quantity,
                    nodes,
                    incoming_by_product[product_key],
                    requirements,
                    bom_by_id,
                    reachable_bom_cache,
                ),
            ))
    return rows


def _default_warehouse(item_type: str) -> tuple[str, str]:
    if item_type in {"part", "assembly"}:
        return WAREHOUSE_CODE_MAIN, WAREHOUSE_NAME_MAIN
    return "—", "成品仓"


def _inventory_item_row(
    item: ProductionPlanItem,
    stock_id: int | None,
    completed_node_label: str,
    warehouse_code: str,
    warehouse_name: str,
    stock_quantity: int,
    reserved_quantity: int,
    available_quantity: int,
    planned_allocation: int,
    item_name: str | None = None,
    decomposition: dict | None = None,
) -> dict:
    return {
        "id": stock_id or -item.id,
        "customer_order_item_id": item.customer_order_item_id,
        "item_type": item.item_type,
        "product_id": item.product_id,
        "product_version": item.product_version,
        "product_bom_id": item.product_bom_id,
        "flow_node_id": item.flow_node_id,
        "item_code": item.item_code,
        "item_name": item_name or item.item_name,
        "completed_node_label": completed_node_label,
        "warehouse_code": warehouse_code,
        "warehouse_name": warehouse_name,
        "stock_quantity": stock_quantity,
        "reserved_quantity": reserved_quantity,
        "available_quantity": available_quantity,
        "planned_allocation_quantity": planned_allocation,
        "allocation_mode": (
            "reservation" if item.item_type == "finished_product" else "outbound"
        ),
        "decomposition": decomposition or {
            "finished_equivalent_quantity": 0,
            "parts": [],
        },
    }

def _inventory_decomposition(
    item: ProductionPlanItem,
    quantity: int,
    nodes: dict[str, dict],
    incoming: dict[str, list[str]],
    requirements: dict[int, int],
    bom_by_id: dict,
    reachable_bom_cache: dict[tuple[int, int, str], set[int]],
) -> dict:
    finished_equivalent = quantity if item.item_type == "finished_product" else (
        quantity // max(item.unit_requirement, 1)
    )
    if item.item_type == "finished_product":
        reachable_bom_ids: set[int] = set()
    elif item.item_type == "part":
        reachable_bom_ids = {item.product_bom_id} if item.product_bom_id is not None else set()
    else:
        cache_key = (item.product_id, item.product_version, item.flow_node_id)
        if cache_key not in reachable_bom_cache:
            reachable_bom_ids: set[int] = set()
            pending = list(incoming.get(item.flow_node_id, []))
            visited: set[str] = set()
            while pending:
                node_id = pending.pop()
                if node_id in visited:
                    continue
                visited.add(node_id)
                node = nodes.get(node_id, {})
                if node.get("type") == "part" and isinstance(node.get("bom_item_id"), int):
                    reachable_bom_ids.add(node["bom_item_id"])
                    continue
                pending.extend(incoming.get(node_id, []))
            reachable_bom_cache[cache_key] = reachable_bom_ids
        reachable_bom_ids = reachable_bom_cache[cache_key]
    parts = []
    for bom_id in sorted(
        reachable_bom_ids,
        key=lambda value: getattr(bom_by_id.get(value), "sort_order", 0),
    ):
        bom = bom_by_id.get(bom_id)
        if bom is None:
            continue
        equivalent_quantity = (
            quantity
            if item.item_type == "part" and item.product_bom_id == bom_id
            else finished_equivalent * requirements.get(bom_id, bom.pcs)
        )
        parts.append({
            "product_bom_id": bom.id,
            "item_code": bom.part_no,
            "item_name": bom.part_name,
            "quantity": equivalent_quantity,
        })
    return {
        "finished_equivalent_quantity": finished_equivalent,
        "parts": parts,
    }
