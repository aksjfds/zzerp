"""Warehouse persistence boundary with a replaceable SQL Server-facing contract."""

from dataclasses import dataclass
from typing import Protocol, Sequence

from sqlalchemy import case, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.time import business_now
from domain.warehouse import (
    WarehouseMaterialIdentity,
    WarehouseStockIdentity,
    WarehouseStockSnapshot,
)
from modules.inventory.persistence import WarehouseStock


class WarehouseWriteRejected(Exception):
    """The warehouse confirmed that no inventory change was made."""


class WarehouseWriteUncertain(Exception):
    """The warehouse cannot confirm whether an external write took effect."""


@dataclass(frozen=True, slots=True)
class WarehouseStockDeduction:
    stock_id: int
    quantity: int


class WarehouseGateway(Protocol):
    def list_stocks(
        self,
        *,
        item_code: str | None = None,
        product_version: int | None = None,
        item_type: str | None = None,
        warehouse_code: str | None = None,
        available_only: bool = False,
    ) -> tuple[WarehouseStockSnapshot, ...]: ...

    def lock_outbound_candidates(
        self,
        *,
        item_code: str,
        product_version: int,
        item_type: str,
        warehouse_code: str,
        completion_status_priority: Sequence[str],
    ) -> tuple[WarehouseStockSnapshot, ...]: ...

    def list_material_stocks(
        self,
        identities: Sequence[WarehouseMaterialIdentity],
        *,
        available_only: bool = False,
    ) -> tuple[WarehouseStockSnapshot, ...]: ...

    def decrease_stocks(
        self,
        deductions: Sequence[WarehouseStockDeduction],
    ) -> tuple[WarehouseStockSnapshot, ...]: ...

    def increase_stock(
        self,
        *,
        identity: WarehouseStockIdentity,
        item_name: str,
        specification: str,
        warehouse_name: str,
        quantity: int,
    ) -> WarehouseStockSnapshot: ...


class PostgreSQLWarehouseGateway:
    """Atomic temporary-warehouse implementation for the current PostgreSQL baseline."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_stocks(
        self,
        *,
        item_code: str | None = None,
        product_version: int | None = None,
        item_type: str | None = None,
        warehouse_code: str | None = None,
        available_only: bool = False,
    ) -> tuple[WarehouseStockSnapshot, ...]:
        statement = select(WarehouseStock)
        if item_code is not None:
            statement = statement.where(WarehouseStock.item_code == item_code)
        if product_version is not None:
            statement = statement.where(WarehouseStock.product_version == product_version)
        if item_type is not None:
            statement = statement.where(WarehouseStock.item_type == item_type)
        if warehouse_code is not None:
            statement = statement.where(WarehouseStock.warehouse_code == warehouse_code)
        if available_only:
            statement = statement.where(WarehouseStock.quantity > 0)
        statement = statement.order_by(
            WarehouseStock.item_code,
            WarehouseStock.product_version,
            WarehouseStock.item_type,
            WarehouseStock.completion_status,
            WarehouseStock.warehouse_code,
            WarehouseStock.id,
        )
        return tuple(_stock_snapshot(stock) for stock in self._session.scalars(statement))

    def lock_outbound_candidates(
        self,
        *,
        item_code: str,
        product_version: int,
        item_type: str,
        warehouse_code: str,
        completion_status_priority: Sequence[str],
    ) -> tuple[WarehouseStockSnapshot, ...]:
        priority = case(
            {status: index for index, status in enumerate(completion_status_priority)},
            value=WarehouseStock.completion_status,
            else_=len(completion_status_priority),
        )
        statement = (
            select(WarehouseStock)
            .where(
                WarehouseStock.item_code == item_code,
                WarehouseStock.product_version == product_version,
                WarehouseStock.item_type == item_type,
                WarehouseStock.warehouse_code == warehouse_code,
                WarehouseStock.completion_status.in_(completion_status_priority),
                WarehouseStock.quantity > 0,
            )
            .order_by(
                priority,
                WarehouseStock.last_inbound_date.asc().nulls_last(),
                WarehouseStock.id,
            )
            .with_for_update()
        )
        return tuple(_stock_snapshot(stock) for stock in self._session.scalars(statement))

    def list_material_stocks(
        self,
        identities: Sequence[WarehouseMaterialIdentity],
        *,
        available_only: bool = False,
    ) -> tuple[WarehouseStockSnapshot, ...]:
        keys = {
            (identity.item_code, identity.product_version, identity.item_type)
            for identity in identities
        }
        if not keys:
            return ()
        statement = select(WarehouseStock).where(
            tuple_(
                WarehouseStock.item_code,
                WarehouseStock.product_version,
                WarehouseStock.item_type,
            ).in_(sorted(keys))
        )
        if available_only:
            statement = statement.where(WarehouseStock.quantity > 0)
        statement = statement.order_by(
            WarehouseStock.item_code,
            WarehouseStock.product_version,
            WarehouseStock.item_type,
            WarehouseStock.completion_status,
            WarehouseStock.warehouse_code,
            WarehouseStock.id,
        )
        return tuple(_stock_snapshot(stock) for stock in self._session.scalars(statement))

    def decrease_stocks(
        self,
        deductions: Sequence[WarehouseStockDeduction],
    ) -> tuple[WarehouseStockSnapshot, ...]:
        changed: list[WarehouseStockSnapshot] = []
        with self._session.begin_nested():
            for deduction in deductions:
                statement = (
                    update(WarehouseStock)
                    .where(
                        WarehouseStock.id == deduction.stock_id,
                        WarehouseStock.quantity >= deduction.quantity,
                    )
                    .values(
                        quantity=WarehouseStock.quantity - deduction.quantity,
                        last_outbound_date=business_now().date(),
                    )
                    .returning(WarehouseStock)
                )
                stock = self._session.scalars(statement).one_or_none()
                if stock is None:
                    raise WarehouseWriteRejected("仓库库存不足或库存记录已发生变化")
                changed.append(_stock_snapshot(stock))
        return tuple(changed)

    def increase_stock(
        self,
        *,
        identity: WarehouseStockIdentity,
        item_name: str,
        specification: str,
        warehouse_name: str,
        quantity: int,
    ) -> WarehouseStockSnapshot:
        statement = insert(WarehouseStock).values(
            item_code=identity.item_code,
            item_name=item_name,
            product_version=identity.product_version,
            item_type=identity.item_type,
            specification=specification,
            inventory_unit="PCS",
            warehouse_code=identity.warehouse_code,
            warehouse_name=warehouse_name,
            quantity=quantity,
            completion_status=identity.completion_status,
            last_inbound_date=business_now().date(),
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_warehouse_stock_identity",
            set_={
                "quantity": WarehouseStock.quantity + statement.excluded.quantity,
                "last_inbound_date": statement.excluded.last_inbound_date,
            },
            where=(
                (WarehouseStock.item_name == statement.excluded.item_name)
                & (WarehouseStock.specification == statement.excluded.specification)
                & (WarehouseStock.inventory_unit == statement.excluded.inventory_unit)
                & (WarehouseStock.warehouse_name == statement.excluded.warehouse_name)
            ),
        ).returning(WarehouseStock)
        stock = self._session.scalars(statement).one_or_none()
        if stock is None:
            raise WarehouseWriteRejected("相同库存身份的品名、规格或仓库名称不一致")
        return _stock_snapshot(stock)


def _stock_snapshot(stock: WarehouseStock) -> WarehouseStockSnapshot:
    return WarehouseStockSnapshot(
        id=stock.id,
        item_code=stock.item_code,
        item_name=stock.item_name,
        product_version=stock.product_version,
        item_type=stock.item_type,
        specification=stock.specification,
        inventory_unit=stock.inventory_unit,
        warehouse_code=stock.warehouse_code,
        warehouse_name=stock.warehouse_name,
        quantity=stock.quantity,
        completion_status=stock.completion_status,
        last_inbound_date=stock.last_inbound_date,
        last_outbound_date=stock.last_outbound_date,
    )


__all__ = [
    "PostgreSQLWarehouseGateway",
    "WarehouseGateway",
    "WarehouseStockDeduction",
    "WarehouseWriteRejected",
    "WarehouseWriteUncertain",
]
