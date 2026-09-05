"""Planning read projection over temporary warehouse and finished inventory."""

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from domain.production_inventory import FinishedStockLookup
from domain.warehouse import WAREHOUSE_CODE_MAIN, WarehouseMaterialIdentity
from modules.inventory.plan_stock_api import list_finished_plan_stocks
from modules.inventory.warehouse_api import list_material_warehouse_stocks
from modules.errors import DomainError
from modules.production_core.material_state_api import MaterialStateView, find_material_states


@dataclass(frozen=True, slots=True)
class PlanStockRow:
    stock_id: int
    identity_key: str
    item_type: str
    item_code: str
    item_name: str
    completion_status: str
    processing_state_id: int | None
    resume_flow_node_id: str | None
    warehouse_code: str
    warehouse_name: str
    stock_quantity: int
    reserved_quantity: int
    available_quantity: int


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
    _load_finished_stocks(session, item_list, result)
    return {key: tuple(rows) for key, rows in result.items()}


def plan_item_available_quantities(
    session: Session,
    items: Iterable,
) -> dict[str, int]:
    return {
        key: sum(row.available_quantity for row in rows)
        for key, rows in load_plan_item_stocks(session, items, {}).items()
    }


def completion_status_priority(
    session: Session,
    item,
    _flow_cache: dict | None = None,
) -> tuple[str, ...]:
    return tuple(state.display_text for state in _material_states(session, item, _flow_cache))


def processing_state_by_status(
    session: Session,
    item,
    _flow_cache: dict | None = None,
) -> dict[str, MaterialStateView]:
    states = _material_states(session, item, _flow_cache)
    by_status = {state.display_text: state for state in states}
    if len(by_status) != len(states):
        raise DomainError(
            "material_processing_state_display_conflict",
            "同一物料存在无法区分的加工状态，请检查工艺命名",
            status_code=409,
        )
    return by_status


def _material_states(
    session,
    item,
    request_cache: dict | None = None,
) -> tuple[MaterialStateView, ...]:
    cache_key = (
        "material-processing-states",
        item.product_id,
        item.product_version,
        item.product_bom_id,
        item.flow_node_id,
    )
    if request_cache is not None and cache_key in request_cache:
        return request_cache[cache_key]
    states = find_material_states(
        session,
        product_id=item.product_id,
        product_version=item.product_version,
        product_bom_id=item.product_bom_id,
        origin_flow_node_id=item.flow_node_id,
    )
    result = tuple(sorted(
        states,
        key=lambda state: (
            len(state.procedure_history),
            state.qc_status in {"released", "stored"},
            state.id,
        ),
        reverse=True,
    ))
    if request_cache is not None:
        request_cache[cache_key] = result
    return result


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
    allowed_states = {
        item.identity_key: processing_state_by_status(session, item, flow_cache)
        for item in material_items
    }
    for stock in stocks:
        if stock.warehouse_code != WAREHOUSE_CODE_MAIN:
            continue
        item = by_material.get((stock.item_code, stock.product_version, stock.item_type))
        if item is None:
            continue
        state = allowed_states[item.identity_key].get(stock.completion_status)
        if state is None:
            continue
        result[item.identity_key].append(PlanStockRow(
            stock_id=stock.id,
            identity_key=item.identity_key,
            item_type=item.item_type,
            item_code=stock.item_code,
            item_name=stock.item_name,
            completion_status=stock.completion_status,
            processing_state_id=state.id,
            resume_flow_node_id=state.resume_flow_node_id,
            warehouse_code=stock.warehouse_code,
            warehouse_name=stock.warehouse_name,
            stock_quantity=stock.quantity,
            reserved_quantity=0,
            available_quantity=stock.quantity,
        ))


def _load_finished_stocks(session, items, result) -> None:
    finished_items = [item for item in items if item.item_type == "finished_product"]
    groups = list_finished_plan_stocks(
        session,
        (
            FinishedStockLookup(
                identity_key=item.identity_key,
                product_id=item.product_id,
                product_version=item.product_version,
            )
            for item in finished_items
        ),
    )
    for item in finished_items:
        for stock in groups.get(item.identity_key, ()):
            result[item.identity_key].append(PlanStockRow(
                stock_id=stock.id,
                identity_key=item.identity_key,
                item_type=item.item_type,
                item_code=stock.item_code,
                item_name=stock.item_name,
                completion_status="成品",
                processing_state_id=None,
                resume_flow_node_id=None,
                warehouse_code="—",
                warehouse_name="成品仓",
                stock_quantity=stock.quantity,
                reserved_quantity=stock.reserved_quantity,
                available_quantity=stock.available_quantity,
            ))


__all__ = [
    "PlanStockRow",
    "completion_status_priority",
    "processing_state_by_status",
    "load_plan_item_stocks",
    "plan_item_available_quantities",
]
