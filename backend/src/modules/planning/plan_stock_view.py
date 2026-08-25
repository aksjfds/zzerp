"""Planning read projection over temporary warehouse and finished inventory."""

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from domain.production_inventory import FinishedStockLookup
from domain.warehouse import WAREHOUSE_CODE_MAIN, WarehouseMaterialIdentity
from modules.inventory.plan_stock_api import list_finished_plan_stocks
from modules.inventory.warehouse_api import list_material_warehouse_stocks
from modules.production_core.flow_api import (
    completed_node_display_label,
    load_product_flow,
    material_completion_steps,
)


@dataclass(frozen=True, slots=True)
class PlanStockRow:
    stock_id: int
    identity_key: str
    item_type: str
    item_code: str
    item_name: str
    completion_status: str
    warehouse_code: str
    warehouse_name: str
    quantity: int


def load_plan_item_stocks(
    session: Session,
    items: Iterable,
    flow_cache: dict | None = None,
) -> dict[str, tuple[PlanStockRow, ...]]:
    item_list = list(items)
    request_flow_cache = flow_cache if flow_cache is not None else {}
    result: dict[str, list[PlanStockRow]] = {
        item.identity_key: [] for item in item_list
    }
    _load_non_finished_stocks(session, item_list, result, request_flow_cache)
    _load_finished_stocks(session, item_list, result, request_flow_cache)
    return {key: tuple(rows) for key, rows in result.items()}


def plan_item_available_quantities(
    session: Session,
    items: Iterable,
) -> dict[str, int]:
    return {
        key: sum(row.quantity for row in rows)
        for key, rows in load_plan_item_stocks(session, items, {}).items()
    }


def completion_status_priority(
    session: Session,
    item,
    flow_cache: dict | None = None,
) -> tuple[str, ...]:
    flow, nodes = load_product_flow(
        session,
        item.product_id,
        item.product_version,
        flow_cache,
    )
    return tuple(
        step.completion_status
        for step in reversed(
            material_completion_steps(flow, nodes, item.flow_node_id)
        )
    )


def completion_node_by_status(
    session: Session,
    item,
    flow_cache: dict | None = None,
) -> dict[str, str]:
    flow, nodes = load_product_flow(
        session,
        item.product_id,
        item.product_version,
        flow_cache,
    )
    return {
        step.completion_status: step.flow_node_id
        for step in material_completion_steps(flow, nodes, item.flow_node_id)
    }


def _load_non_finished_stocks(session, items, result, flow_cache: dict) -> None:
    material_items = [item for item in items if item.item_type in {"part", "assembly"}]
    stocks = list_material_warehouse_stocks(
        session,
        tuple(
            WarehouseMaterialIdentity(
                item_code=item.item_code,
                product_version=item.product_version,
                item_type=item.item_type,
            )
            for item in material_items
        ),
        available_only=True,
    )
    by_material = {
        (item.item_code, item.product_version, item.item_type): item
        for item in material_items
    }
    allowed_statuses = {
        item.identity_key: set(completion_status_priority(session, item, flow_cache))
        for item in material_items
    }
    for stock in stocks:
        if stock.warehouse_code != WAREHOUSE_CODE_MAIN:
            continue
        item = by_material.get((stock.item_code, stock.product_version, stock.item_type))
        if item is None or stock.completion_status not in allowed_statuses[item.identity_key]:
            continue
        result[item.identity_key].append(PlanStockRow(
            stock_id=stock.id,
            identity_key=item.identity_key,
            item_type=item.item_type,
            item_code=stock.item_code,
            item_name=stock.item_name,
            completion_status=stock.completion_status,
            warehouse_code=stock.warehouse_code,
            warehouse_name=stock.warehouse_name,
            quantity=stock.quantity,
        ))


def _load_finished_stocks(session, items, result, flow_cache: dict) -> None:
    finished_items = [item for item in items if item.item_type == "finished_product"]
    groups = list_finished_plan_stocks(
        session,
        (
            FinishedStockLookup(
                identity_key=item.identity_key,
                product_id=item.product_id,
                product_version=item.product_version,
                flow_node_id=item.flow_node_id,
            )
            for item in finished_items
        ),
    )
    flow_contexts = {
        (item.product_id, item.product_version): load_product_flow(
            session,
            item.product_id,
            item.product_version,
            flow_cache,
        )
        for item in finished_items
    }
    for item in finished_items:
        flow, nodes = flow_contexts[(item.product_id, item.product_version)]
        for stock in groups.get(item.identity_key, ()):
            quantity = stock.quantity
            if quantity <= 0:
                continue
            result[item.identity_key].append(PlanStockRow(
                stock_id=stock.id,
                identity_key=item.identity_key,
                item_type=item.item_type,
                item_code=stock.item_code,
                item_name=stock.item_name,
                completion_status=completed_node_display_label(
                    flow,
                    nodes,
                    stock.flow_node_id,
                    stock.completed_flow_node_id,
                ),
                warehouse_code="finished",
                warehouse_name="成品仓",
                quantity=quantity,
            ))


__all__ = [
    "PlanStockRow",
    "completion_node_by_status",
    "completion_status_priority",
    "load_plan_item_stocks",
    "plan_item_available_quantities",
]
