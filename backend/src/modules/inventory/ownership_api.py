"""Inventory-owner commands for cross-order finished inventory."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.time import utc_now
from modules.errors import DomainError
from modules.inventory.persistence import (
    FinishedInventoryStock,
    FinishedInventoryTransaction,
)


def receive_finished_surplus(
    session: Session,
    *,
    product_id: int,
    product_version: int,
    flow_node_id: str,
    completed_flow_node_id: str,
    item_code: str,
    item_name: str,
    quantity: int,
    source_production_item_id: int,
    actor_username: str,
    reason: str,
) -> FinishedInventoryStock:
    if quantity <= 0:
        raise DomainError(
            "finished_inventory_quantity_invalid",
            "成品入库数量必须大于0",
        )
    stock = session.scalars(
        insert(FinishedInventoryStock)
        .values(
            product_id=product_id,
            product_version=product_version,
            flow_node_id=flow_node_id,
            completed_flow_node_id=completed_flow_node_id,
            item_code=item_code,
            item_name=item_name,
            quantity=quantity,
        )
        .on_conflict_do_update(
            constraint="uq_finished_inventory_stock_identity",
            set_={
                "item_code": item_code,
                "item_name": item_name,
                "quantity": FinishedInventoryStock.quantity + quantity,
                "revision": FinishedInventoryStock.revision + 1,
                "updated_at": utc_now(),
            },
        )
        .returning(FinishedInventoryStock)
    ).one()
    before_quantity = stock.quantity - quantity
    session.add(FinishedInventoryTransaction(
        finished_inventory_stock_id=stock.id,
        source_production_item_id=source_production_item_id,
        transaction_type="receipt",
        quantity=quantity,
        quantity_before=before_quantity,
        quantity_after=stock.quantity,
        actor_username=actor_username,
        reason=reason,
    ))
    return stock


__all__ = ["receive_finished_surplus"]
