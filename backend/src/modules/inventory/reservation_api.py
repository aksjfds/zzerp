"""Transaction-aware stock availability and production-plan reservations."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.time import utc_now
from modules.errors import DomainError
from modules.inventory.persistence import (
    InventoryReservation,
    InventoryStock,
    InventoryTransaction,
)


def available_quantity(session: Session, identity_key: str) -> int:
    stock = session.scalar(
        select(InventoryStock).where(InventoryStock.identity_key == identity_key)
    )
    return max((stock.quantity - stock.reserved_quantity) if stock else 0, 0)


def available_quantities(
    session: Session,
    identity_keys: Iterable[str],
) -> dict[str, int]:
    keys = set(identity_keys)
    if not keys:
        return {}
    return {
        stock.identity_key: max(stock.quantity - stock.reserved_quantity, 0)
        for stock in session.scalars(
            select(InventoryStock).where(InventoryStock.identity_key.in_(keys))
        )
    }


def reserve_plan_item(
    session: Session,
    *,
    production_plan_id: int,
    production_plan_item_id: int,
    identity_key: str,
    requested_quantity: int,
    actor_username: str,
) -> int:
    if requested_quantity <= 0:
        return 0
    stock = session.scalar(
        select(InventoryStock)
        .where(InventoryStock.identity_key == identity_key)
        .with_for_update()
    )
    if stock is None:
        return 0
    allocatable = min(
        requested_quantity,
        max(stock.quantity - stock.reserved_quantity, 0),
    )
    if allocatable <= 0:
        return 0
    before_reserved = stock.reserved_quantity
    stock.reserved_quantity += allocatable
    stock.revision += 1
    stock.updated_at = utc_now()
    reservation = InventoryReservation(
        production_plan_id=production_plan_id,
        production_plan_item_id=production_plan_item_id,
        inventory_stock_id=stock.id,
        reserved_quantity=allocatable,
    )
    session.add(reservation)
    session.flush()
    session.add(InventoryTransaction(
        inventory_stock_id=stock.id,
        production_plan_id=production_plan_id,
        production_plan_item_id=production_plan_item_id,
        inventory_reservation_id=reservation.id,
        transaction_type="reserve",
        quantity=allocatable,
        quantity_before=stock.quantity,
        quantity_after=stock.quantity,
        reserved_before=before_reserved,
        reserved_after=stock.reserved_quantity,
        actor_username=actor_username,
        reason="生产计划确认自动占用",
    ))
    return allocatable


def release_plan_reservations(
    session: Session,
    production_plan_id: int,
    actor_username: str,
) -> None:
    reservations = list(session.scalars(
        select(InventoryReservation)
        .where(
            InventoryReservation.production_plan_id == production_plan_id,
            InventoryReservation.status.in_(("reserved", "issued")),
        )
        .order_by(InventoryReservation.id)
        .with_for_update()
    ))
    if any(item.issued_quantity > 0 for item in reservations):
        raise DomainError(
            "production_plan_inventory_issued",
            "该生产计划已有库存出库，暂不支持取消",
            status_code=409,
        )
    for reservation in reservations:
        stock = session.get(InventoryStock, reservation.inventory_stock_id, with_for_update=True)
        if stock is None:
            raise DomainError("inventory_stock_missing", "占用的库存记录不存在", status_code=409)
        before_reserved = stock.reserved_quantity
        stock.reserved_quantity -= reservation.reserved_quantity
        stock.revision += 1
        stock.updated_at = utc_now()
        reservation.status = "released"
        reservation.released_at = utc_now()
        session.add(InventoryTransaction(
            inventory_stock_id=stock.id,
            production_plan_id=production_plan_id,
            production_plan_item_id=reservation.production_plan_item_id,
            inventory_reservation_id=reservation.id,
            transaction_type="release",
            quantity=reservation.reserved_quantity,
            quantity_before=stock.quantity,
            quantity_after=stock.quantity,
            reserved_before=before_reserved,
            reserved_after=stock.reserved_quantity,
            actor_username=actor_username,
            reason="取消生产计划自动解除占用",
        ))


def plan_has_issued_inventory(session: Session, production_plan_id: int) -> bool:
    return session.scalar(
        select(InventoryReservation.id)
        .where(
            InventoryReservation.production_plan_id == production_plan_id,
            InventoryReservation.issued_quantity > 0,
        )
        .limit(1)
    ) is not None


def issue_plan_reservations(
    session: Session,
    *,
    production_plan_id: int,
    department_code: str,
    quantities: dict[int, int],
    actor_username: str,
) -> None:
    from modules.planning.model_api import ProductionPlanItem

    reservations = list(session.scalars(
        select(InventoryReservation)
        .join(InventoryStock, InventoryStock.id == InventoryReservation.inventory_stock_id)
        .where(
            InventoryReservation.production_plan_id == production_plan_id,
            InventoryReservation.status.in_(("reserved", "issued")),
            InventoryStock.department_code == department_code,
        )
        .order_by(InventoryReservation.id)
        .with_for_update()
    ))
    expected_ids = {item.id for item in reservations}
    if not reservations:
        raise DomainError("inventory_reservation_not_found", "该生产计划没有可出库的占用", status_code=404)
    if set(quantities) != expected_ids:
        raise DomainError(
            "inventory_issue_items_incomplete",
            "必须提交该生产计划在本部门的全部占用项目",
            path="items",
        )
    for reservation in reservations:
        quantity = quantities[reservation.id]
        remaining = reservation.reserved_quantity - reservation.issued_quantity
        if quantity < 0 or quantity > remaining:
            raise DomainError(
                "inventory_issue_quantity_invalid",
                "出库数量不能超过尚未出库的占用数量",
                path="items",
            )
        if quantity == 0:
            continue
        stock = session.get(InventoryStock, reservation.inventory_stock_id, with_for_update=True)
        if stock is None or stock.quantity < quantity or stock.reserved_quantity < quantity:
            raise DomainError(
                "inventory_stock_changed",
                "库存数量已变化，请重新加载后再出库",
                status_code=409,
            )
        plan_item = session.get(
            ProductionPlanItem,
            reservation.production_plan_item_id,
            with_for_update=True,
        )
        if plan_item is None:
            raise DomainError("production_plan_item_not_found", "生产计划项目不存在", status_code=409)
        before_quantity = stock.quantity
        before_reserved = stock.reserved_quantity
        stock.quantity -= quantity
        stock.reserved_quantity -= quantity
        stock.revision += 1
        stock.updated_at = utc_now()
        reservation.issued_quantity += quantity
        reservation.issued_at = utc_now()
        reservation.issued_by = actor_username
        reservation.status = "issued"
        plan_item.issued_inventory_quantity += quantity
        from modules.production_core.inventory_api import accept_issued_inventory
        accept_issued_inventory(session, plan_item, quantity, actor_username)
        session.add(InventoryTransaction(
            inventory_stock_id=stock.id,
            production_plan_id=production_plan_id,
            production_plan_item_id=plan_item.id,
            inventory_reservation_id=reservation.id,
            transaction_type="issue",
            quantity=quantity,
            quantity_before=before_quantity,
            quantity_after=stock.quantity,
            reserved_before=before_reserved,
            reserved_after=stock.reserved_quantity,
            actor_username=actor_username,
            reason="按生产计划出库",
        ))


__all__ = [
    "available_quantities",
    "available_quantity",
    "issue_plan_reservations",
    "plan_has_issued_inventory",
    "release_plan_reservations",
    "reserve_plan_item",
]
