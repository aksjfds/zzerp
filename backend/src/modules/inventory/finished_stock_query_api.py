"""Read models for unified finished stock, reservations, and transactions."""

from sqlalchemy import select

from database import SessionLocal
from modules.engineering.model_api import Product
from modules.inventory.persistence import (
    FinishedStock,
    FinishedStockReservation,
    FinishedStockTransaction,
)
from modules.sales.model_api import CustomerOrder, CustomerOrderItem


def list_finished_stocks() -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(FinishedStock, Product)
            .join(Product, Product.id == FinishedStock.product_id)
            .order_by(Product.factory_code, FinishedStock.product_version)
        )
        return [
            {
                "id": stock.id,
                "product_id": stock.product_id,
                "product_version": stock.product_version,
                "item_code": product.factory_code,
                "item_name": product.product_name,
                "quantity": stock.quantity,
                "reserved_quantity": stock.reserved_quantity,
                "available_quantity": stock.quantity - stock.reserved_quantity,
                "revision": stock.revision,
                "updated_at": stock.updated_at,
            }
            for stock, product in rows
        ]


def list_finished_stock_reservations(
    *,
    production_plan_id: int | None = None,
    customer_order_item_id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    with SessionLocal() as session:
        statement = (
            select(
                FinishedStockReservation,
                FinishedStock,
                Product,
                CustomerOrder,
            )
            .join(
                FinishedStock,
                FinishedStock.id == FinishedStockReservation.finished_stock_id,
            )
            .join(Product, Product.id == FinishedStock.product_id)
            .join(
                CustomerOrderItem,
                CustomerOrderItem.id
                == FinishedStockReservation.customer_order_item_id,
            )
            .join(
                CustomerOrder,
                CustomerOrder.id == CustomerOrderItem.customer_order_id,
            )
        )
        if production_plan_id is not None:
            statement = statement.where(
                FinishedStockReservation.production_plan_id == production_plan_id
            )
        if customer_order_item_id is not None:
            statement = statement.where(
                FinishedStockReservation.customer_order_item_id
                == customer_order_item_id
            )
        statement = statement.order_by(
            FinishedStockReservation.created_at.desc(),
            FinishedStockReservation.id.desc(),
        ).limit(limit)
        return [
            {
                "id": reservation.id,
                "finished_stock_id": stock.id,
                "production_plan_id": reservation.production_plan_id,
                "production_plan_item_id": reservation.production_plan_item_id,
                "customer_order_id": order.id,
                "customer_order_no": order.customer_order_no,
                "customer_order_item_id": reservation.customer_order_item_id,
                "product_id": stock.product_id,
                "product_version": stock.product_version,
                "item_code": product.factory_code,
                "item_name": product.product_name,
                "reserved_quantity": reservation.reserved_quantity,
                "shipped_quantity": reservation.shipped_quantity,
                "released_quantity": reservation.released_quantity,
                "open_quantity": (
                    reservation.reserved_quantity
                    - reservation.shipped_quantity
                    - reservation.released_quantity
                ),
                "created_at": reservation.created_at,
                "updated_at": reservation.updated_at,
            }
            for reservation, stock, product, order in session.execute(statement)
        ]


def list_finished_stock_transactions(
    *,
    finished_stock_id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    with SessionLocal() as session:
        statement = (
            select(FinishedStockTransaction, FinishedStock, Product, CustomerOrder)
            .join(
                FinishedStock,
                FinishedStock.id == FinishedStockTransaction.finished_stock_id,
            )
            .join(Product, Product.id == FinishedStock.product_id)
            .outerjoin(
                CustomerOrder,
                CustomerOrder.id == FinishedStockTransaction.customer_order_id,
            )
        )
        if finished_stock_id is not None:
            statement = statement.where(
                FinishedStockTransaction.finished_stock_id == finished_stock_id
            )
        statement = statement.order_by(
            FinishedStockTransaction.created_at.desc(),
            FinishedStockTransaction.id.desc(),
        ).limit(limit)
        return [
            {
                "id": transaction.id,
                "finished_stock_id": stock.id,
                "finished_receipt_id": transaction.finished_receipt_id,
                "finished_stock_reservation_id": (
                    transaction.finished_stock_reservation_id
                ),
                "operation_group_no": transaction.operation_group_no,
                "reversal_of_transaction_id": transaction.reversal_of_transaction_id,
                "customer_order_id": transaction.customer_order_id,
                "customer_order_no": order.customer_order_no if order else "",
                "customer_order_item_id": transaction.customer_order_item_id,
                "product_id": stock.product_id,
                "product_version": stock.product_version,
                "item_code": product.factory_code,
                "item_name": product.product_name,
                "transaction_type": transaction.transaction_type,
                "quantity": transaction.quantity,
                "quantity_before": transaction.quantity_before,
                "quantity_after": transaction.quantity_after,
                "actor_username": transaction.actor_username,
                "reason": transaction.reason or "",
                "created_at": transaction.created_at,
            }
            for transaction, stock, product, order in session.execute(statement)
        ]


__all__ = [
    "list_finished_stock_reservations",
    "list_finished_stock_transactions",
    "list_finished_stocks",
]
