"""Read-only query-model surface for inventory persistence.

Collaborating modules may use these models to compose set-based read queries.
Inventory mutations remain owned by inventory transaction and ownership APIs.
"""

from modules.inventory.persistence import (
    InventoryReceipt,
    InventoryReservation,
    InventoryStock,
    InventoryTransaction,
    FinishedOrderStock,
    FinishedGoodsTransaction,
)

__all__ = [
    "InventoryReceipt",
    "InventoryReservation",
    "InventoryStock",
    "InventoryTransaction",
    "FinishedOrderStock",
    "FinishedGoodsTransaction",
]
