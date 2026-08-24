from __future__ import annotations

"""Production-plan loading and revision guards."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from modules.errors import DomainError
from modules.planning.persistence import ProductionPlan

def _load_plan(
    session: Session,
    order_id: int,
    *,
    for_update: bool = False,
) -> ProductionPlan | None:
    statement = (
        select(ProductionPlan)
        .options(selectinload(ProductionPlan.items))
        .where(ProductionPlan.customer_order_id == order_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)

def _ensure_revision(plan: ProductionPlan, expected_revision: int) -> None:
    if plan.revision != expected_revision:
        raise DomainError(
            "production_plan_revision_conflict",
            "生产计划已发生变化，请重新加载",
            status_code=409,
        )
