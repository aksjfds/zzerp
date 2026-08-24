from __future__ import annotations

"""Production-plan BOM output validation."""

from sqlalchemy.orm import Session
from modules.errors import DomainError
from modules.planning.persistence import ProductionPlanItem
from modules.planning.plan_builder import planned_finished_quantity

def _validate_product_output(session: Session, items: list[ProductionPlanItem]) -> None:
    groups: dict[int, list[ProductionPlanItem]] = {}
    for item in items:
        groups.setdefault(item.customer_order_item_id, []).append(item)
    for group in groups.values():
        finished = next(item for item in group if item.item_type == "finished_product")
        supported_quantity = planned_finished_quantity(session, group)
        if supported_quantity < finished.gross_required_quantity:
            raise DomainError(
                "planned_quantity_insufficient",
                f"{finished.item_code} {finished.item_name}按 BOM 最多可满足 "
                f"{supported_quantity} 件，少于订单需求 {finished.gross_required_quantity} 件",
                path="items",
            )
