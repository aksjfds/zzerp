from sqlalchemy import func, select
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.planning.persistence import (
    DepartmentWorkOrder,
    DepartmentWorkOrderMovement,
    ProductionPlan,
)
from zzerp.modules.planning.serializers import serialize_plans


def ensure_plan_without_movements(session, plan_id: int) -> None:
    exists = session.scalar(
        select(DepartmentWorkOrderMovement.id)
        .join(
            DepartmentWorkOrder, DepartmentWorkOrder.id == DepartmentWorkOrderMovement.work_order_id
        )
        .where(DepartmentWorkOrder.production_plan_id == plan_id)
        .limit(1)
    )
    if exists is not None:
        raise DomainError(
            "plan_has_material_movements",
            "计划已有到料或出料流水，不能撤回、重建或删除工单",
            status_code=409,
        )


def load_plan(session, plan_id: int, *, for_update: bool = False) -> ProductionPlan:
    statement = select(ProductionPlan).where(ProductionPlan.id == plan_id)
    if for_update:
        statement = statement.with_for_update()
    plan = session.scalar(statement)
    if plan is None:
        raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
    return plan


def list_plans(session: Session, page: int, page_size: int) -> tuple[list[dict], int]:
    plans = list(
        session.scalars(
            select(ProductionPlan)
            .order_by(ProductionPlan.updated_at.desc(), ProductionPlan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    total = session.scalar(select(func.count()).select_from(ProductionPlan)) or 0
    return serialize_plans(session, plans), total


def get_plan(session: Session, plan_id: int) -> dict:
    return serialize_plans(session, [load_plan(session, plan_id)])[0]
