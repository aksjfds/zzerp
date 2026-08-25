"""Read-only product-version reference checks owned by inventory."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.persistence import FinishedInventoryStock


def has_product_version_inventory_reference(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    return session.scalar(
        select(FinishedInventoryStock.id).where(
            FinishedInventoryStock.product_id == product_id,
            FinishedInventoryStock.product_version == product_version,
        ).limit(1)
    ) is not None


__all__ = ["has_product_version_inventory_reference"]
