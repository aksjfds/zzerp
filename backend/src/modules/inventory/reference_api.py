"""Read-only product-version reference checks owned by inventory."""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.persistence import FinishedReceipt, FinishedStock


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
            ).where(FinishedReceipt.work_order_batch_id.in_(work_order_batch_ids))
        )
    }


__all__ = [
    "finished_receipt_states_by_qc_batch",
    "has_product_version_inventory_reference",
]
