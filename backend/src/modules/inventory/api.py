"""Public API for cross-order inventory queries and production-plan issues."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from modules.inventory.finished_goods_api import (
    confirm_finished_order_receipt,
    list_finished_order_stocks,
    ship_finished_order_item,
)
from modules.inventory.persistence import (
    InventoryStock,
    InventoryTransaction,
    FinishedGoodsTransaction,
)
from modules.production_core.flow_api import completed_node_display_label, load_product_flow
from modules.sales.model_api import CustomerOrder
from modules.inventory.persistence import FinishedOrderStock


def list_stocks(department_code: str | None = None) -> list[dict]:
    with SessionLocal() as session:
        statement = select(InventoryStock).order_by(InventoryStock.item_code, InventoryStock.id)
        if department_code:
            statement = statement.where(InventoryStock.department_code == department_code)
        stocks = list(session.scalars(statement))
        flow_contexts = _load_stock_flow_contexts(session, stocks)
        return [_serialize_stock(item, flow_contexts) for item in stocks]


def list_transactions(
    department_code: str,
    stock_id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    with SessionLocal() as session:
        statement = (
            select(InventoryTransaction)
            .join(InventoryStock, InventoryStock.id == InventoryTransaction.inventory_stock_id)
            .where(InventoryStock.department_code == department_code)
        )
        if stock_id:
            statement = statement.where(InventoryTransaction.inventory_stock_id == stock_id)
        statement = statement.order_by(InventoryTransaction.id.desc()).limit(limit)
        result_rows = list(session.execute(statement.add_columns(InventoryStock)))
        flow_contexts = _load_stock_flow_contexts(
            session,
            [stock for _, stock in result_rows],
        )
        rows = [
            {
                "id": item.id,
                "source_type": "inventory_stock",
                "source_id": stock.id,
                "inventory_stock_id": item.inventory_stock_id,
                "production_plan_id": item.production_plan_id,
                "transaction_type": item.transaction_type,
                "quantity": item.quantity,
                "quantity_before": item.quantity_before,
                "quantity_after": item.quantity_after,
                "reserved_before": item.reserved_before,
                "reserved_after": item.reserved_after,
                "actor_username": item.actor_username,
                "reason": item.reason or "",
                "created_at": item.created_at.isoformat(),
                "item_code": stock.item_code,
                "item_name": stock.item_name,
                "customer_order_no": "",
                "completed_node_label": _completed_node_label(stock, flow_contexts),
            }
            for item, stock in result_rows
        ]
        if department_code == "finished":
            rows.extend(_finished_order_transactions(session, limit))
        return sorted(
            rows,
            key=lambda item: (item["created_at"], item["id"]),
            reverse=True,
        )[:limit]


def _finished_order_transactions(session: Session, limit: int) -> list[dict]:
    statement = (
        select(
            FinishedGoodsTransaction,
            FinishedOrderStock,
            CustomerOrder,
        )
        .select_from(FinishedGoodsTransaction)
        .join(
            FinishedOrderStock,
            FinishedOrderStock.id == FinishedGoodsTransaction.finished_order_stock_id,
        )
        .join(CustomerOrder, CustomerOrder.id == FinishedOrderStock.customer_order_id)
        .order_by(FinishedGoodsTransaction.created_at.desc(), FinishedGoodsTransaction.id.desc())
        .limit(limit)
    )
    rows: list[dict] = []
    for transaction, lot, order in session.execute(statement):
        rows.append({
            "id": transaction.id,
            "source_type": "finished_order_stock",
            "source_id": lot.id,
            "inventory_stock_id": None,
            "production_plan_id": None,
            "transaction_type": transaction.transaction_type,
            "quantity": transaction.quantity,
            "quantity_before": transaction.quantity_before,
            "quantity_after": transaction.quantity_after,
            "reserved_before": 0,
            "reserved_after": 0,
            "actor_username": transaction.actor_username,
            "reason": transaction.reason or "",
            "created_at": transaction.created_at.isoformat(),
            "item_code": lot.item_code,
            "item_name": lot.item_name,
            "customer_order_no": order.customer_order_no,
        })
    return rows


def _load_stock_flow_contexts(
    session: Session,
    stocks: list[InventoryStock],
) -> dict[tuple[int, int], tuple[dict, dict[str, dict]]]:
    return {
        key: load_product_flow(session, *key)
        for key in {(item.product_id, item.product_version) for item in stocks}
    }


def _completed_node_label(
    item: InventoryStock,
    flow_contexts: dict[tuple[int, int], tuple[dict, dict[str, dict]]],
) -> str:
    flow, nodes = flow_contexts[(item.product_id, item.product_version)]
    return completed_node_display_label(
        flow,
        nodes,
        item.flow_node_id,
        item.completed_flow_node_id,
    )


def _serialize_stock(
    item: InventoryStock,
    flow_contexts: dict[tuple[int, int], tuple[dict, dict[str, dict]]],
) -> dict:
    return {
        "id": item.id,
        "department_code": item.department_code,
        "item_type": item.item_type,
        "product_id": item.product_id,
        "product_version": item.product_version,
        "product_bom_id": item.product_bom_id,
        "flow_node_id": item.flow_node_id,
        "completed_flow_node_id": item.completed_flow_node_id,
        "completed_node_label": _completed_node_label(item, flow_contexts),
        "item_code": item.item_code,
        "item_name": item.item_name,
        "quantity": item.quantity,
        "reserved_quantity": item.reserved_quantity,
        "available_quantity": item.quantity - item.reserved_quantity,
        "revision": item.revision,
    }


__all__ = [
    "confirm_finished_order_receipt",
    "list_finished_order_stocks",
    "list_stocks",
    "list_transactions",
    "ship_finished_order_item",
]
