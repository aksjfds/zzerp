"""Read-only product-version reference checks owned by inventory."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.persistence import InventoryReceipt, InventoryStock


def has_product_version_inventory_reference(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    if session.scalar(
        select(InventoryStock.id).where(
            InventoryStock.product_id == product_id,
            InventoryStock.product_version == product_version,
        ).limit(1)
    ) is not None:
        return True
    return session.scalar(
        select(InventoryReceipt.id).where(
            InventoryReceipt.product_id == product_id,
            InventoryReceipt.product_version == product_version,
        ).limit(1)
    ) is not None


__all__ = ["has_product_version_inventory_reference"]
