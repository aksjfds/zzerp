"""Read-only reference checks and projections owned by production core."""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.production_core.persistence import ProductionItem, WorkOrder
from modules.production_core.card_status import reserved_quantities


def reserved_repository_quantities(
    session: Session,
    repository_ids: Collection[int],
) -> dict[int, int]:
    return reserved_quantities(session, list(repository_ids))


def has_product_version_production_reference(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    return bool(
        session.scalar(
            select(ProductionItem.id)
            .where(
                ProductionItem.product_id == product_id,
                ProductionItem.product_version == product_version,
            )
            .limit(1)
        )
    )


def list_standard_execution_config_keys(
    session: Session,
    product_ids: Collection[int],
    procedure_ids: Collection[int],
) -> set[tuple[int, int, str, str, int]]:
    if not product_ids or not procedure_ids:
        return set()
    return set(
        session.execute(
            select(
                ProductionItem.product_id,
                ProductionItem.product_version,
                ProductionItem.origin_flow_node_id,
                WorkOrder.flow_node_id,
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
    flow_node_id: str,
    procedure_id: int,
) -> bool:
    return session.scalar(
        select(WorkOrder.id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            ProductionItem.product_id == product_id,
            ProductionItem.product_version == product_version,
            ProductionItem.origin_flow_node_id == origin_flow_node_id,
            WorkOrder.flow_node_id == flow_node_id,
            WorkOrder.procedure_id == procedure_id,
        )
        .limit(1)
    ) is not None


def list_standard_execution_order_ids(
    session: Session,
    *,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
) -> list[int]:
    return list(session.scalars(
        select(WorkOrder.id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            ProductionItem.product_id == product_id,
            ProductionItem.product_version == product_version,
            ProductionItem.origin_flow_node_id == origin_flow_node_id,
            WorkOrder.flow_node_id == flow_node_id,
        )
        .order_by(WorkOrder.id)
    ))


def has_work_order_for_procedure(session: Session, procedure_id: int) -> bool:
    return session.scalar(
        select(WorkOrder.id)
        .where(WorkOrder.procedure_id == procedure_id)
        .limit(1)
    ) is not None


__all__ = [
    "has_product_version_production_reference",
    "has_standard_execution_order",
    "has_work_order_for_procedure",
    "list_standard_execution_order_ids",
    "list_standard_execution_config_keys",
    "reserved_repository_quantities",
]
