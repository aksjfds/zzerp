from database import SessionLocal
from domain.time import utc_now
from schemas.planning import ProductionPlanCreate, ProductionPlanUpdate
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from modules.errors import DomainError
from modules.planning.material_movements import ensure_plan_without_movements
from modules.planning.persistence import (
    DepartmentWorkOrder,
    ProductionPlan,
    ProductionPlanItem,
)
from modules.planning.queries import load_plan
from modules.planning.serializers import serialize_plans
from modules.planning.snapshots import create_snapshot_routes, prepare_snapshots
from modules.planning.work_orders import rebuild_work_orders


def ensure_revision(plan: ProductionPlan, expected_revision: int) -> None:
    if plan.revision != expected_revision:
        raise DomainError(
            "production_plan_revision_conflict",
            "生产计划已被其他用户更新，请重新加载",
            status_code=409,
        )


def create_plan_items(session, plan, items, snapshots):
    for item in items:
        record = ProductionPlanItem(production_plan_id=plan.id, customer_id=plan.customer_id,
                                    **item.model_dump(exclude={"source_version"}), **snapshots[item.product_id])
        session.add(record)
        session.flush()
        create_snapshot_routes(session, record)
    session.flush()


def raise_plan_integrity_error(exc: IntegrityError) -> None:
    constraint = getattr(
        getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", ""
    )
    if constraint == "uq_production_plan_order_no":
        raise DomainError(
            "production_plan_order_no_conflict", "订单号已存在", status_code=409,
            path="order_no",
        ) from exc
    raise exc


def create_plan(payload: ProductionPlanCreate) -> dict:
    try:
        with SessionLocal.begin() as session:
            snapshots = prepare_snapshots(session, payload)
            plan = ProductionPlan(**payload.model_dump(exclude={"items"}))
            session.add(plan)
            session.flush()
            create_plan_items(session, plan, payload.items, snapshots)
            return serialize_plans(session, [plan])[0]
    except IntegrityError as exc:
        raise_plan_integrity_error(exc)


def update_plan(plan_id: int, payload: ProductionPlanUpdate) -> dict:
    try:
        with SessionLocal.begin() as session:
            plan = load_plan(session, plan_id, for_update=True)
            ensure_revision(plan, payload.expected_revision)
            if plan.status not in {"draft", "cancelled"}:
                raise DomainError(
                    "production_plan_not_editable", "只有草稿或已取消计划允许修改",
                    status_code=409,
                )
            ensure_plan_without_movements(session, plan.id)
            snapshots = prepare_snapshots(session, payload, plan)
            # Remove old customer-bound details before changing the plan customer.
            session.execute(delete(DepartmentWorkOrder).where(DepartmentWorkOrder.production_plan_id == plan.id))
            session.flush()
            session.execute(delete(ProductionPlanItem).where(ProductionPlanItem.production_plan_id == plan.id))
            for field, value in payload.model_dump(exclude={"expected_revision", "items"}).items():
                setattr(plan, field, value)
            plan.status = "draft"
            plan.confirmed_at = None
            plan.confirmed_by = None
            plan.revision += 1
            plan.updated_at = utc_now()
            session.flush()
            create_plan_items(session, plan, payload.items, snapshots)
            return serialize_plans(session, [plan])[0]
    except IntegrityError as exc:
        raise_plan_integrity_error(exc)


TRANSITIONS = {
    "confirm": ("draft", "confirmed"),
    "unconfirm": ("confirmed", "draft"),
    "complete": ("confirmed", "completed"),
    "reopen": ("completed", "confirmed"),
}


def change_plan_status(
    plan_id: int, action: str, expected_revision: int, actor_username: str,
) -> dict:
    with SessionLocal.begin() as session:
        plan = load_plan(session, plan_id, for_update=True)
        ensure_revision(plan, expected_revision)
        if action == "cancel":
            if plan.status not in {"draft", "confirmed"}:
                raise DomainError("production_plan_invalid_status", "当前计划不能取消", status_code=409)
            target = "cancelled"
        else:
            transition = TRANSITIONS.get(action)
            if transition is None or plan.status != transition[0]:
                raise DomainError("production_plan_invalid_status", "当前计划不允许此操作", status_code=409)
            target = transition[1]
        now = utc_now()
        if action == "unconfirm":
            ensure_plan_without_movements(session, plan.id)
            session.execute(delete(DepartmentWorkOrder).where(
                DepartmentWorkOrder.production_plan_id == plan.id))
        if action == "confirm":
            rebuild_work_orders(session, plan)
            plan.confirmed_at = now
            plan.confirmed_by = actor_username
        elif action == "unconfirm":
            plan.confirmed_at = None
            plan.confirmed_by = None
        elif action == "complete":
            plan.completed_at = now
            plan.completed_by = actor_username
        elif action == "reopen":
            plan.completed_at = None
            plan.completed_by = None
        plan.status = target
        plan.revision += 1
        plan.updated_at = now
        session.flush()
        return serialize_plans(session, [plan])[0]


def delete_plan(plan_id: int, expected_revision: int) -> None:
    with SessionLocal.begin() as session:
        plan = load_plan(session, plan_id, for_update=True)
        ensure_revision(plan, expected_revision)
        if plan.status not in {"draft", "cancelled"}:
            raise DomainError(
                "production_plan_not_deletable", "只有草稿或已取消计划允许删除",
                status_code=409,
            )
        ensure_plan_without_movements(session, plan.id)
        session.delete(plan)
