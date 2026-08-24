"""Inventory-owner commands used by production and planning workflows."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.time import utc_now
from modules.errors import DomainError
from modules.inventory.persistence import (
    InventoryReceipt,
    InventoryStock,
    InventoryTransaction,
)


def create_receipt(
    session: Session,
    *,
    department_code: str,
    item_type: str,
    product_id: int,
    product_version: int,
    product_bom_id: int | None,
    flow_node_id: str,
    completed_flow_node_id: str,
    item_code: str,
    item_name: str,
    quantity: int,
    source_customer_order_id: int | None = None,
    source_customer_order_item_id: int | None = None,
    source_production_item_id: int | None = None,
) -> InventoryReceipt:
    if quantity <= 0:
        raise DomainError("inventory_receipt_quantity_invalid", "入库数量必须大于0")
    valid_location = (
        (department_code == "finished" and item_type == "finished_product")
        or (department_code == "warehouse" and item_type in {"part", "assembly"})
    )
    if not valid_location:
        raise DomainError("inventory_receipt_location_invalid", "库存类型与入库部门不匹配")
    receipt = InventoryReceipt(
        department_code=department_code,
        item_type=item_type,
        product_id=product_id,
        product_version=product_version,
        product_bom_id=product_bom_id,
        flow_node_id=flow_node_id,
        completed_flow_node_id=completed_flow_node_id,
        item_code=item_code,
        item_name=item_name,
        quantity=quantity,
        source_customer_order_id=source_customer_order_id,
        source_customer_order_item_id=source_customer_order_item_id,
        source_production_item_id=source_production_item_id,
    )
    session.add(receipt)
    session.flush()
    return receipt


def confirm_receipt(
    session: Session,
    receipt_id: int,
    actor_username: str,
    reason: str,
) -> InventoryStock:
    receipt = session.get(InventoryReceipt, receipt_id, with_for_update=True)
    if receipt is None:
        raise DomainError("inventory_receipt_not_found", "待入库记录不存在", status_code=404)
    if receipt.status != "pending":
        raise DomainError("inventory_receipt_not_pending", "该入库记录已处理", status_code=409)
    stock = session.scalar(
        select(InventoryStock)
        .where(
            InventoryStock.department_code == receipt.department_code,
            InventoryStock.item_type == receipt.item_type,
            InventoryStock.product_id == receipt.product_id,
            InventoryStock.product_version == receipt.product_version,
            InventoryStock.product_bom_id == receipt.product_bom_id,
            InventoryStock.flow_node_id == receipt.flow_node_id,
            InventoryStock.completed_flow_node_id == receipt.completed_flow_node_id,
        )
        .with_for_update()
    )
    if stock is None:
        stock = InventoryStock(
            department_code=receipt.department_code,
            item_type=receipt.item_type,
            product_id=receipt.product_id,
            product_version=receipt.product_version,
            product_bom_id=receipt.product_bom_id,
            flow_node_id=receipt.flow_node_id,
            completed_flow_node_id=receipt.completed_flow_node_id,
            item_code=receipt.item_code,
            item_name=receipt.item_name,
            quantity=0,
            reserved_quantity=0,
        )
        session.add(stock)
        session.flush()
    before_quantity = stock.quantity
    stock.quantity += receipt.quantity
    stock.revision += 1
    stock.updated_at = utc_now()
    receipt.status = "confirmed"
    receipt.confirmed_at = utc_now()
    receipt.confirmed_by = actor_username
    session.add(InventoryTransaction(
        inventory_stock_id=stock.id,
        inventory_receipt_id=receipt.id,
        transaction_type="receipt",
        quantity=receipt.quantity,
        quantity_before=before_quantity,
        quantity_after=stock.quantity,
        reserved_before=stock.reserved_quantity,
        reserved_after=stock.reserved_quantity,
        actor_username=actor_username,
        reason=reason,
    ))
    return stock


__all__ = ["confirm_receipt", "create_receipt"]
