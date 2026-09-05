"""Stable planning references exposed to collaborating modules."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from modules.planning.plan_builder import planned_product_quantity
from modules.planning.persistence import ProductionPlan, ProductionPlanItem


@dataclass(frozen=True)
class FinishedInboundPlanSummary:
    product_id: int
    product_version: int
    item_code: str
    item_name: str
    planned_quantity: int
    production_plan_count: int
    updated_at: datetime


def list_finished_inbound_plan_summaries(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> tuple[list[FinishedInboundPlanSummary], int]:
    """Aggregate non-cancelled production plans by finished-stock identity."""
    conditions = (
        ProductionPlan.status != "cancelled",
        ProductionPlanItem.item_type == "finished_product",
    )
    identities = (
        select(ProductionPlanItem.product_id, ProductionPlanItem.product_version)
        .join(
            ProductionPlan,
            ProductionPlan.id == ProductionPlanItem.production_plan_id,
        )
        .where(*conditions)
        .group_by(ProductionPlanItem.product_id, ProductionPlanItem.product_version)
    )
    total = int(
        session.scalar(select(func.count()).select_from(identities.subquery())) or 0
    )
    selected_identities = list(session.execute(
        identities.order_by(
            func.max(ProductionPlan.updated_at).desc(),
            ProductionPlanItem.product_id,
            ProductionPlanItem.product_version,
        )
        .offset(offset)
        .limit(limit)
    ))
    identity_keys = [(product_id, version) for product_id, version in selected_identities]
    if not identity_keys:
        return [], total
    plan_groups: dict[
        tuple[int, int],
        tuple[ProductionPlan, list[ProductionPlanItem]],
    ] = {}
    for plan, item in session.execute(
        select(ProductionPlan, ProductionPlanItem)
        .join(
            ProductionPlanItem,
            ProductionPlanItem.production_plan_id == ProductionPlan.id,
        )
        .where(
            ProductionPlan.status != "cancelled",
            tuple_(ProductionPlanItem.product_id, ProductionPlanItem.product_version).in_(
                identity_keys
            ),
        )
        .order_by(ProductionPlan.id, ProductionPlanItem.sort_order)
    ):
        group_key = (plan.id, item.customer_order_item_id)
        plan_groups.setdefault(group_key, (plan, []))[1].append(item)

    totals: dict[tuple[int, int], dict] = {}
    for plan, items in plan_groups.values():
        finished = next(item for item in items if item.item_type == "finished_product")
        key = (finished.product_id, finished.product_version)
        summary = totals.setdefault(
            key,
            {
                "item_code": finished.item_code,
                "item_name": finished.item_name,
                "planned_quantity": 0,
                "production_plan_count": 0,
                "updated_at": plan.updated_at,
            },
        )
        summary["planned_quantity"] += _planned_inbound_quantity(plan, finished, items)
        summary["production_plan_count"] += 1
        summary["updated_at"] = max(summary["updated_at"], plan.updated_at)
    return [
        FinishedInboundPlanSummary(
            product_id=product_id,
            product_version=version,
            **totals[(product_id, version)],
        )
        for product_id, version in identity_keys
    ], total


def _planned_inbound_quantity(
    plan: ProductionPlan,
    finished: ProductionPlanItem,
    items: list[ProductionPlanItem],
) -> int:
    stock_quantity = (
        finished.estimated_inventory_quantity
        if plan.status == "draft"
        else finished.allocated_inventory_quantity
    )
    return max(planned_product_quantity(items) - stock_quantity, 0)


def list_executable_assembly_plan_quantities(
    session: Session,
    customer_order_item_ids: Collection[int],
) -> list[tuple[int, str, int]]:
    """Return confirmed or completed plan quantities for assembly execution."""
    if not customer_order_item_ids:
        return []
    return [
        (order_item_id, flow_node_id, int(planned_quantity))
        for order_item_id, flow_node_id, planned_quantity in session.execute(
            select(
                ProductionPlanItem.customer_order_item_id,
                ProductionPlanItem.flow_node_id,
                ProductionPlanItem.planned_production_quantity,
            )
            .join(
                ProductionPlan,
                ProductionPlan.id == ProductionPlanItem.production_plan_id,
            )
            .where(
                ProductionPlan.status.in_(("confirmed", "completed")),
                ProductionPlanItem.item_type == "assembly",
                ProductionPlanItem.customer_order_item_id.in_(
                    customer_order_item_ids
                ),
            )
        )
    ]


__all__ = [
    "FinishedInboundPlanSummary",
    "list_executable_assembly_plan_quantities",
    "list_finished_inbound_plan_summaries",
]
