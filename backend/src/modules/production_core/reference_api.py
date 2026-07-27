"""Read-only reference checks and projections owned by production core."""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.production_core.persistence import ProductionItem, WorkOrder


def has_production_items_for_boms(
    session: Session,
    product_bom_ids: Collection[int],
) -> bool:
    if not product_bom_ids:
        return False
    return bool(
        session.scalar(
            select(ProductionItem.id)
            .where(ProductionItem.product_bom_id.in_(product_bom_ids))
            .limit(1)
        )
    )


def list_standard_execution_config_keys(
    session: Session,
    product_ids: Collection[int],
    procedure_ids: Collection[int],
) -> set[tuple[int, int, str, int]]:
    if not product_ids or not procedure_ids:
        return set()
    return set(
        session.execute(
            select(
                ProductionItem.product_id,
                ProductionItem.product_version,
                ProductionItem.origin_flow_node_id,
                WorkOrder.procedure_id,
            )
            .join(WorkOrder, WorkOrder.production_item_id == ProductionItem.id)
            .where(
                ProductionItem.product_id.in_(product_ids),
                WorkOrder.procedure_id.in_(procedure_ids),
            )
        ).all()
    )


def has_standard_execution_order(
    session: Session,
    *,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    procedure_id: int,
) -> bool:
    return session.scalar(
        select(WorkOrder.id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            ProductionItem.product_id == product_id,
            ProductionItem.product_version == product_version,
            ProductionItem.origin_flow_node_id == origin_flow_node_id,
            WorkOrder.procedure_id == procedure_id,
        )
        .limit(1)
    ) is not None


__all__ = [
    "has_production_items_for_boms",
    "has_standard_execution_order",
    "list_standard_execution_config_keys",
]
