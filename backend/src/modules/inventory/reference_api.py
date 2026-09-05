"""Read-only product-version reference checks owned by inventory."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from modules.inventory.persistence import FinishedReceipt, FinishedStock


@dataclass(frozen=True)
class PendingFinishedReceipt:
    id: int
    work_order_batch_id: int | None
    work_order_id: int | None
    quantity: int
    created_at: datetime


@dataclass(frozen=True)
class FinishedArrivalSummary:
    arrived_quantity: int
    pending_receipts: tuple[PendingFinishedReceipt, ...]


def finished_arrival_summaries(
    session: Session,
    product_versions: Collection[tuple[int, int]],
) -> dict[tuple[int, int], FinishedArrivalSummary]:
    keys = set(product_versions)
    if not keys:
        return {}
    identity_condition = tuple_(
        FinishedReceipt.product_id,
        FinishedReceipt.product_version,
    ).in_(keys)
    arrived = {
        (product_id, version): int(quantity)
        for product_id, version, quantity in session.execute(
            select(
                FinishedReceipt.product_id,
                FinishedReceipt.product_version,
                func.sum(FinishedReceipt.quantity),
            )
            .where(
                identity_condition,
                FinishedReceipt.status.in_(("pending", "received")),
            )
            .group_by(FinishedReceipt.product_id, FinishedReceipt.product_version)
        )
    }
    pending: dict[tuple[int, int], list[PendingFinishedReceipt]] = {
        key: [] for key in keys
    }
    for receipt in session.scalars(
        select(FinishedReceipt)
        .where(identity_condition, FinishedReceipt.status == "pending")
        .order_by(FinishedReceipt.created_at, FinishedReceipt.id)
    ):
        pending[(receipt.product_id, receipt.product_version)].append(
            PendingFinishedReceipt(
                id=receipt.id,
                work_order_batch_id=receipt.work_order_batch_id,
                work_order_id=receipt.work_order_id,
                quantity=receipt.quantity,
                created_at=receipt.created_at,
            )
        )
    return {
        key: FinishedArrivalSummary(
            arrived_quantity=arrived.get(key, 0),
            pending_receipts=tuple(pending[key]),
        )
        for key in keys
    }


def has_product_version_inventory_reference(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    stock_exists = session.scalar(
        select(FinishedStock.id).where(
            FinishedStock.product_id == product_id,
            FinishedStock.product_version == product_version,
        ).limit(1)
    ) is not None
    if stock_exists:
        return True
    return session.scalar(
        select(FinishedReceipt.id).where(
            FinishedReceipt.product_id == product_id,
            FinishedReceipt.product_version == product_version,
        ).limit(1)
    ) is not None


def finished_receipt_states_by_qc_batch(
    session: Session,
    work_order_batch_ids: Collection[int],
) -> dict[int, tuple[str, int]]:
    if not work_order_batch_ids:
        return {}
    return {
        batch_id: (status, quantity)
        for batch_id, status, quantity in session.execute(
            select(
                FinishedReceipt.work_order_batch_id,
                FinishedReceipt.status,
                FinishedReceipt.quantity,
            ).where(
                FinishedReceipt.work_order_batch_id.in_(work_order_batch_ids),
                FinishedReceipt.status.in_(("pending", "received")),
            )
        )
    }


__all__ = [
    "FinishedArrivalSummary",
    "PendingFinishedReceipt",
    "finished_arrival_summaries",
    "finished_receipt_states_by_qc_batch",
    "has_product_version_inventory_reference",
]
