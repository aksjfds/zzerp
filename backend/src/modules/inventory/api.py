"""Public HTTP-facing temporary warehouse and unified finished-stock operations."""

from collections.abc import Sequence
from dataclasses import asdict

from database import SessionLocal
from domain.warehouse import WarehouseOperationSnapshot, WarehouseOperationStatus
from modules.inventory.finished_receipt_api import (
    confirm_finished_receipt,
    list_finished_receipts,
)
from modules.inventory.finished_shipment_api import (
    list_finished_shipment_candidates,
    ship_finished_order_item,
)
from modules.inventory.finished_stock_query_api import (
    list_finished_stock_reservations,
    list_finished_stock_transactions,
    list_finished_stocks,
)
from modules.inventory.warehouse_api import (
    list_warehouse_operations as list_operation_snapshots,
    list_warehouse_stocks as list_stock_snapshots,
    review_uncertain_warehouse_operation,
)


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


__all__ = [
    "confirm_finished_receipt",
    "list_finished_receipts",
    "list_finished_shipment_candidates",
    "list_project_warehouse_operations",
    "list_finished_stock_reservations",
    "list_finished_stock_transactions",
    "list_finished_stocks",
    "list_temporary_warehouse_stocks",
    "review_project_warehouse_operation",
    "ship_finished_order_item",
]
