from sqlalchemy import func, select

from database import SessionLocal
from modules.errors import DomainError
from modules.planning.persistence import ProductionPlan
from modules.planning.serializers import serialize_plans


def load_plan(session, plan_id: int, *, for_update: bool = False) -> ProductionPlan:
    statement = select(ProductionPlan).where(ProductionPlan.id == plan_id)
    if for_update:
        statement = statement.with_for_update()
    plan = session.scalar(statement)
    if plan is None:
        raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
    return plan


def list_plans(page: int, page_size: int) -> tuple[list[dict], int]:
    with SessionLocal() as session:
        plans = list(session.scalars(
            select(ProductionPlan)
            .order_by(ProductionPlan.updated_at.desc(), ProductionPlan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ))
        total = session.scalar(select(func.count()).select_from(ProductionPlan)) or 0
        return serialize_plans(session, plans), total


def get_plan(plan_id: int) -> dict:
    with SessionLocal() as session:
        return serialize_plans(session, [load_plan(session, plan_id)])[0]
