from database import SessionLocal
from sqlalchemy import func, select

from modules.errors import DomainError
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
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


def get_plan_product_snapshot(plan_id: int, product_id: int, *, department_scope: str | None) -> dict:
    if department_scope is not None:
        raise DomainError("plan_snapshot_access_denied", "生产账号仅可查看所属部门工单", status_code=403)
    with SessionLocal() as session:
        item = session.get(ProductionPlanItem, (plan_id, product_id))
        if item is None:
            raise DomainError("plan_snapshot_not_found", "计划产品快照不存在", status_code=404)
        return {
            "product_id": item.product_id, "source_version": item.source_version,
            "source_version_value": item.source_version_value,
            "product_name": item.product_name, "factory_code": item.factory_code,
            "customer_code": item.customer_code, "bom_items": item.bom_snapshot,
            "process_flow": item.process_flow_snapshot,
        }
