"""Public HTTP-facing inventory queries and finished-goods operations."""

from collections.abc import Sequence
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.warehouse import WarehouseOperationSnapshot, WarehouseOperationStatus
from modules.inventory.finished_goods_api import (
    confirm_finished_order_receipt,
    list_finished_order_stocks,
    ship_finished_order_item,
)
from modules.inventory.persistence import (
    FinishedInventoryStock,
    FinishedInventoryTransaction,
    FinishedGoodsTransaction,
    FinishedOrderStock,
)
from modules.inventory.warehouse_api import (
    list_warehouse_operations as list_operation_snapshots,
    list_warehouse_stocks as list_stock_snapshots,
    review_uncertain_warehouse_operation,
)
from modules.production_core.flow_api import completed_node_display_label, load_product_flow
from modules.sales.model_api import CustomerOrder


def list_temporary_warehouse_stocks() -> list[dict]:
    with SessionLocal() as session:
        return [
            asdict(stock)
            for stock in list_stock_snapshots(session)
        ]


def list_project_warehouse_operations(
    status: WarehouseOperationStatus | None = None,
    limit: int = 200,
) -> list[dict]:
    with SessionLocal() as session:
        operations = list_operation_snapshots(
            session,
            status=status,
            limit=limit,
        )
        return _serialize_warehouse_operations(operations)


def review_project_warehouse_operation(
    operation_group_no: str,
    reviewer_username: str,
    review_note: str,
) -> list[dict]:
    with SessionLocal.begin() as session:
        return _serialize_warehouse_operations(
            review_uncertain_warehouse_operation(
                session,
                operation_group_no=operation_group_no,
                reviewer_username=reviewer_username,
                review_note=review_note,
            )
        )


def _serialize_warehouse_operations(
    operations: Sequence[WarehouseOperationSnapshot],
) -> list[dict]:
    reviewable_by_group: dict[str, int] = {}
    for operation in operations:
        if operation.status != "uncertain" or operation.manual_reviewed_at is not None:
            continue
        current = reviewable_by_group.get(operation.operation_group_no)
        if current is None or operation.id < current:
            reviewable_by_group[operation.operation_group_no] = operation.id
    return [
        {
            **asdict(operation),
            "can_review": (
                reviewable_by_group.get(operation.operation_group_no) == operation.id
            ),
        }
        for operation in operations
    ]


def list_finished_inventory_stocks() -> list[dict]:
    with SessionLocal() as session:
        statement = select(FinishedInventoryStock).order_by(
            FinishedInventoryStock.item_code,
            FinishedInventoryStock.id,
        )
        stocks = list(session.scalars(statement))
        flow_contexts = _load_stock_flow_contexts(session, stocks)
        return [_serialize_stock(item, flow_contexts) for item in stocks]


def list_finished_inventory_transactions(
    stock_id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    with SessionLocal() as session:
        statement = (
            select(FinishedInventoryTransaction)
            .join(
                FinishedInventoryStock,
                FinishedInventoryStock.id
                == FinishedInventoryTransaction.finished_inventory_stock_id,
            )
        )
        if stock_id:
            statement = statement.where(
                FinishedInventoryTransaction.finished_inventory_stock_id == stock_id
            )
        statement = statement.order_by(FinishedInventoryTransaction.id.desc()).limit(limit)
        result_rows = list(session.execute(statement.add_columns(FinishedInventoryStock)))
        flow_contexts = _load_stock_flow_contexts(
            session,
            [stock for _, stock in result_rows],
        )
        rows = [
            {
                "id": item.id,
                "source_type": "finished_inventory_stock",
                "source_id": stock.id,
                "finished_inventory_stock_id": item.finished_inventory_stock_id,
                "production_plan_id": item.production_plan_id,
                "transaction_type": item.transaction_type,
                "quantity": item.quantity,
                "quantity_before": item.quantity_before,
                "quantity_after": item.quantity_after,
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
            "finished_inventory_stock_id": None,
            "production_plan_id": None,
            "transaction_type": transaction.transaction_type,
            "quantity": transaction.quantity,
            "quantity_before": transaction.quantity_before,
            "quantity_after": transaction.quantity_after,
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
    stocks: list[FinishedInventoryStock],
) -> dict[tuple[int, int], tuple[dict, dict[str, dict]]]:
    return {
        key: load_product_flow(session, *key)
        for key in {(item.product_id, item.product_version) for item in stocks}
    }


def _completed_node_label(
    item: FinishedInventoryStock,
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
    item: FinishedInventoryStock,
    flow_contexts: dict[tuple[int, int], tuple[dict, dict[str, dict]]],
) -> dict:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "product_version": item.product_version,
        "flow_node_id": item.flow_node_id,
        "completed_flow_node_id": item.completed_flow_node_id,
        "completed_node_label": _completed_node_label(item, flow_contexts),
        "item_code": item.item_code,
        "item_name": item.item_name,
        "quantity": item.quantity,
        "available_quantity": item.quantity,
        "revision": item.revision,
    }


__all__ = [
    "confirm_finished_order_receipt",
    "list_finished_order_stocks",
    "list_project_warehouse_operations",
    "list_finished_inventory_stocks",
    "list_temporary_warehouse_stocks",
    "list_finished_inventory_transactions",
    "review_project_warehouse_operation",
    "ship_finished_order_item",
]
