"""Production-core context required by assembly workflows."""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.production_types import WORK_ORDER_STATUS_CLOSED
from domain.time import utc_now
from modules.engineering.model_api import ProductBom
from modules.production_core.context_api import (
    InventorySourceContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.persistence import ProductionItem, Repository, WorkOrder
from modules.production_core.work_order_support import production_item_unit_quantity


def load_repositories(
    session: Session,
    repository_ids: Collection[int],
    *,
    for_update: bool = False,
) -> list[InventorySourceContext]:
    if not repository_ids:
        return []
    statement = (
        select(Repository)
        .where(Repository.id.in_(repository_ids))
        .order_by(Repository.id)
    )
    if for_update:
        statement = statement.with_for_update()
    return list(session.scalars(statement).all())


def load_production_item(
    session: Session,
    production_item_id: int,
    *,
    for_update: bool = False,
) -> ProductionItemContext | None:
    return session.get(
        ProductionItem,
        production_item_id,
        with_for_update=for_update,
    )


def load_production_items(
    session: Session,
    production_item_ids: Collection[int],
) -> dict[int, ProductionItemContext]:
    if not production_item_ids:
        return {}
    return {
        item.id: item
        for item in session.scalars(
            select(ProductionItem).where(ProductionItem.id.in_(production_item_ids))
        )
    }


def load_assembly_work_order(
    session: Session,
    work_order_id: int,
    *,
    for_update: bool = False,
) -> WorkOrderContext | None:
    return session.get(
        WorkOrder,
        work_order_id,
        with_for_update=for_update,
    )


def assembly_item_unit_quantity(
    session: Session,
    production_item: ProductionItemContext,
) -> int:
    bom_item = (
        session.get(ProductBom, production_item.product_bom_id)
        if production_item.product_bom_id
        else None
    )
    return production_item_unit_quantity(session, production_item, bom_item)


def assign_assembly_work_order_number(
    order: WorkOrder,
    work_order_no: str,
) -> None:
    order.work_order_no = work_order_no


def record_assembly_output(
    order: WorkOrder,
    *,
    completed_quantity: int,
    close_order: bool,
) -> None:
    order.completed_quantity += completed_quantity
    if close_order:
        order.status = WORK_ORDER_STATUS_CLOSED
        order.closed_at = utc_now()


__all__ = [
    "assembly_item_unit_quantity",
    "assign_assembly_work_order_number",
    "load_assembly_work_order",
    "load_production_item",
    "load_production_items",
    "load_repositories",
    "record_assembly_output",
]
