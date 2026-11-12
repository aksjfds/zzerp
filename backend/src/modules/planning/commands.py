from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from domain.time import utc_now
from modules.engineering.product_reference_api import resolve_plan_product
from modules.errors import DomainError
from modules.planning.persistence import ProductionPlan
from modules.planning.queries import load_plan
from modules.planning.serializers import serialize_plans
from modules.sales.customer_api import resolve_customer
from modules.planning.work_orders import rebuild_work_orders
from modules.planning.material_movements import ensure_plan_without_movements
from schemas.planning import ProductionPlanCreate, ProductionPlanUpdate


def ensure_revision(plan: ProductionPlan, expected_revision: int) -> None:
    if plan.revision != expected_revision:
        raise DomainError(
            "production_plan_revision_conflict",
            "生产计划已被其他用户更新，请重新加载",
            status_code=409,
        )


def validate_plan_product(session, payload: ProductionPlanCreate) -> None:
    resolve_plan_product(session, payload.product_id, payload.customer_id)
    resolve_customer(session, payload.customer_id, None, allow_create=False)


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
            validate_plan_product(session, payload)
            plan = ProductionPlan(**payload.model_dump())
            session.add(plan)
            session.flush()
            rebuild_work_orders(session, plan)
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
            validate_plan_product(session, payload)
            for field, value in payload.model_dump(exclude={"expected_revision"}).items():
                setattr(plan, field, value)
            plan.status = "draft"
            plan.confirmed_at = None
            plan.confirmed_by = None
            plan.revision += 1
            plan.updated_at = utc_now()
            rebuild_work_orders(session, plan)
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
        if action == "confirm":
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
