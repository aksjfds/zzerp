"""Inventory-owner API for production-plan finished-stock reservations."""

from collections.abc import Iterable

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from domain.production_inventory import (
    FinishedStockLookup,
    FinishedStockSnapshot,
    IssuedPlanItem,
)
from domain.time import utc_now
from modules.engineering.model_api import Product
from modules.errors import DomainError
from modules.inventory.persistence import FinishedStock, FinishedStockReservation


def list_finished_plan_stocks(
    session: Session,
    lookups: Iterable[FinishedStockLookup],
) -> dict[str, tuple[FinishedStockSnapshot, ...]]:
    lookup_list = list(lookups)
    keys = {
        (lookup.product_id, lookup.product_version)
        for lookup in lookup_list
    }
    if not keys:
        return {}
    rows = list(session.execute(
        select(FinishedStock, Product)
        .join(Product, Product.id == FinishedStock.product_id)
        .where(
            tuple_(
                FinishedStock.product_id,
                FinishedStock.product_version,
            ).in_(sorted(keys)),
        )
        .order_by(FinishedStock.id)
    ))
    return {
        lookup.identity_key: tuple(
            _finished_snapshot(stock, product)
            for stock, product in rows
            if stock.product_id == lookup.product_id
            and stock.product_version == lookup.product_version
        )
        for lookup in lookup_list
    }


def reserve_finished_plan_stock(
    session: Session,
    *,
    production_plan_id: int,
    plan_item: IssuedPlanItem,
    requested_quantity: int,
) -> int:
    if requested_quantity <= 0:
        return 0
    stock = session.scalar(
        select(FinishedStock)
        .where(
            FinishedStock.product_id == plan_item.product_id,
            FinishedStock.product_version == plan_item.product_version,
        )
        .with_for_update()
    )
    if stock is None or stock.quantity - stock.reserved_quantity < requested_quantity:
        raise DomainError(
            "production_plan_finished_stock_changed",
            "成品可用库存已变化，请重新加载生产计划",
            status_code=409,
            path="items",
        )
    stock.reserved_quantity += requested_quantity
    stock.revision += 1
    stock.updated_at = utc_now()
    session.add(FinishedStockReservation(
        finished_stock_id=stock.id,
        production_plan_id=production_plan_id,
        production_plan_item_id=plan_item.id,
        customer_order_item_id=plan_item.customer_order_item_id,
        reserved_quantity=requested_quantity,
    ))
    session.flush()
    return requested_quantity


def finished_plan_reservation_quantities(
    session: Session,
    production_plan_id: int,
) -> dict[tuple[int, int], int]:
    reservations = session.scalars(
        select(FinishedStockReservation).where(
            FinishedStockReservation.production_plan_id == production_plan_id
        )
    )
    return {
        (item.production_plan_item_id, item.finished_stock_id): (
            item.reserved_quantity - item.shipped_quantity - item.released_quantity
        )
        for item in reservations
    }


def release_finished_plan_stock(session: Session, production_plan_id: int) -> None:
    reservation_contexts = list(session.execute(
        select(
            FinishedStockReservation.id,
            FinishedStockReservation.finished_stock_id,
        )
        .where(FinishedStockReservation.production_plan_id == production_plan_id)
        .order_by(
            FinishedStockReservation.finished_stock_id,
            FinishedStockReservation.id,
        )
    ))
    if not reservation_contexts:
        return
    stock_ids = sorted({stock_id for _, stock_id in reservation_contexts})
    stocks = {
        stock.id: stock
        for stock in session.scalars(
            select(FinishedStock)
            .where(FinishedStock.id.in_(stock_ids))
            .order_by(FinishedStock.id)
            .with_for_update()
        )
    }
    reservations = list(session.scalars(
        select(FinishedStockReservation)
        .where(
            FinishedStockReservation.id.in_(
                [reservation_id for reservation_id, _ in reservation_contexts]
            )
        )
        .order_by(
            FinishedStockReservation.finished_stock_id,
            FinishedStockReservation.id,
        )
        .with_for_update()
    ))
    if any(item.shipped_quantity > 0 for item in reservations):
        raise DomainError(
            "production_plan_finished_stock_shipped",
            "生产计划已经使用成品库存发货，不能取消",
            status_code=409,
        )
    now = utc_now()
    for reservation in reservations:
        open_quantity = (
            reservation.reserved_quantity
            - reservation.shipped_quantity
            - reservation.released_quantity
        )
        if open_quantity <= 0:
            continue
        stock = stocks.get(reservation.finished_stock_id)
        if stock is None or stock.reserved_quantity < open_quantity:
            raise DomainError(
                "production_plan_finished_stock_balance_invalid",
                "成品库存占用账实不一致",
                status_code=409,
            )
        stock.reserved_quantity -= open_quantity
        stock.revision += 1
        stock.updated_at = now
        reservation.released_quantity += open_quantity
        reservation.updated_at = now
    session.flush()


def _finished_snapshot(stock: FinishedStock, product: Product) -> FinishedStockSnapshot:
    available_quantity = stock.quantity - stock.reserved_quantity
    return FinishedStockSnapshot(
        id=stock.id,
        product_id=stock.product_id,
        product_version=stock.product_version,
        item_code=product.factory_code,
        item_name=product.product_name,
        quantity=stock.quantity,
        reserved_quantity=stock.reserved_quantity,
        available_quantity=available_quantity,
    )


__all__ = [
    "finished_plan_reservation_quantities",
    "list_finished_plan_stocks",
    "release_finished_plan_stock",
    "reserve_finished_plan_stock",
]
