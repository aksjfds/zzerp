"""Inventory-owner API for direct finished-stock use during plan confirmation."""

from collections.abc import Iterable

from sqlalchemy import select, tuple_, update
from sqlalchemy.orm import Session

from domain.production_inventory import (
    FinishedInventoryStockSnapshot,
    FinishedStockLookup,
    IssuedInventoryStock,
    IssuedPlanItem,
)
from domain.time import utc_now
from modules.errors import DomainError
from modules.inventory.persistence import (
    FinishedInventoryStock,
    FinishedInventoryTransaction,
)


def list_finished_plan_stocks(
    session: Session,
    lookups: Iterable[FinishedStockLookup],
) -> dict[str, tuple[FinishedInventoryStockSnapshot, ...]]:
    lookup_list = list(lookups)
    keys = {
        (lookup.product_id, lookup.product_version, lookup.flow_node_id)
        for lookup in lookup_list
    }
    if not keys:
        return {}
    stocks = list(session.scalars(
        select(FinishedInventoryStock)
        .where(
            tuple_(
                FinishedInventoryStock.product_id,
                FinishedInventoryStock.product_version,
                FinishedInventoryStock.flow_node_id,
            ).in_(sorted(keys)),
        )
        .order_by(FinishedInventoryStock.id)
    ))
    return {
        lookup.identity_key: tuple(
            _finished_snapshot(stock)
            for stock in stocks
            if stock.product_id == lookup.product_id
            and stock.product_version == lookup.product_version
            and stock.flow_node_id == lookup.flow_node_id
        )
        for lookup in lookup_list
    }


def withdraw_finished_plan_stock(
    session: Session,
    *,
    production_plan_id: int,
    plan_item: IssuedPlanItem,
    requested_quantity: int,
    actor_username: str,
) -> tuple[IssuedInventoryStock, ...]:
    if requested_quantity <= 0:
        return ()
    stocks = list(session.scalars(
        select(FinishedInventoryStock)
        .where(
            FinishedInventoryStock.product_id == plan_item.product_id,
            FinishedInventoryStock.product_version == plan_item.product_version,
            FinishedInventoryStock.flow_node_id == plan_item.flow_node_id,
        )
        .order_by(FinishedInventoryStock.id)
        .with_for_update()
    ))
    available = sum(stock.quantity for stock in stocks)
    if available < requested_quantity:
        raise DomainError(
            "production_plan_finished_inventory_changed",
            "成品库存已变化，请重新加载生产计划",
            status_code=409,
        )

    remaining = requested_quantity
    issued: list[IssuedInventoryStock] = []
    for stock in stocks:
        quantity = min(remaining, stock.quantity)
        if quantity <= 0:
            continue
        before_quantity = stock.quantity
        statement = (
            update(FinishedInventoryStock)
            .where(
                FinishedInventoryStock.id == stock.id,
                FinishedInventoryStock.quantity >= quantity,
            )
            .values(
                quantity=FinishedInventoryStock.quantity - quantity,
                revision=FinishedInventoryStock.revision + 1,
                updated_at=utc_now(),
            )
            .returning(FinishedInventoryStock)
        )
        changed = session.scalars(statement).one_or_none()
        if changed is None:
            raise DomainError(
                "production_plan_finished_inventory_changed",
                "成品库存已变化，请重新加载生产计划",
                status_code=409,
            )
        result = IssuedInventoryStock(
            production_plan_item_id=plan_item.id,
            stock_id=changed.id,
            product_id=changed.product_id,
            product_version=changed.product_version,
            flow_node_id=changed.flow_node_id,
            completed_flow_node_id=changed.completed_flow_node_id,
            quantity=quantity,
            quantity_before=before_quantity,
            quantity_after=changed.quantity,
        )
        issued.append(result)
        session.add(FinishedInventoryTransaction(
            finished_inventory_stock_id=changed.id,
            production_plan_id=production_plan_id,
            production_plan_item_id=plan_item.id,
            transaction_type="issue",
            quantity=quantity,
            quantity_before=before_quantity,
            quantity_after=changed.quantity,
            actor_username=actor_username,
            reason="生产计划确认直接扣减成品库存",
        ))
        remaining -= quantity
        if remaining == 0:
            break
    return tuple(issued)


def _finished_snapshot(stock: FinishedInventoryStock) -> FinishedInventoryStockSnapshot:
    return FinishedInventoryStockSnapshot(
        id=stock.id,
        product_id=stock.product_id,
        product_version=stock.product_version,
        flow_node_id=stock.flow_node_id,
        completed_flow_node_id=stock.completed_flow_node_id,
        item_code=stock.item_code,
        item_name=stock.item_name,
        quantity=stock.quantity,
    )


__all__ = ["list_finished_plan_stocks", "withdraw_finished_plan_stock"]
