from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from zzerp.errors import DomainError
from zzerp.modules.engineering.api import ensure_plan_appearance, resolve_plan_product
from zzerp.modules.planning.contracts import ProductionPlanCreate, ProductionPlanUpdate
from zzerp.modules.planning.persistence import (
    DepartmentWorkOrder,
    ProductionPlan,
    ProductionPlanItem,
)
from zzerp.modules.planning.queries import ensure_plan_without_movements, load_plan
from zzerp.modules.planning.serializers import serialize_plans
from zzerp.modules.planning.work_orders import rebuild_work_orders
from zzerp.modules.sales.api import resolve_customer
from zzerp.time import utc_now


def ensure_revision(plan: ProductionPlan, expected_revision: int) -> None:
    if plan.revision != expected_revision:
        raise DomainError(
            "production_plan_revision_conflict",
            "生产计划已被其他用户更新，请重新加载",
            status_code=409,
        )


def validate_plan_products(session, payload: ProductionPlanCreate, plan=None) -> None:
    selected_ids = {item.product_id for item in payload.items}
    product_ids = set(selected_ids)
    if plan is not None:
        product_ids.update(
            session.scalars(
                select(ProductionPlanItem.product_id).where(
                    ProductionPlanItem.production_plan_id == plan.id
                )
            )
        )
    for product_id in sorted(product_ids):
        customer_id = payload.customer_id if product_id in selected_ids else plan.customer_id
        resolve_plan_product(session, product_id, customer_id)
    for item in payload.items:
        ensure_plan_appearance(session, item.product_id, item.appearance_id)
    resolve_customer(session, payload.customer_id, None, allow_create=False)


def create_plan_items(session, plan, items):
    for item in items:
        session.add(
            ProductionPlanItem(
                production_plan_id=plan.id, customer_id=plan.customer_id, **item.model_dump()
            )
        )
    session.flush()
    rebuild_work_orders(session, plan)


def raise_plan_integrity_error(exc: IntegrityError) -> None:
    constraint = getattr(getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", "")
    if constraint == "uq_production_plan_order_no":
        raise DomainError(
            "production_plan_order_no_conflict",
            "订单号已存在",
            status_code=409,
            path="order_no",
        ) from exc
    raise exc


def create_plan(session: Session, payload: ProductionPlanCreate) -> dict:
    try:
        validate_plan_products(session, payload)
        plan = ProductionPlan(**payload.model_dump(exclude={"items"}))
        session.add(plan)
        session.flush()
        create_plan_items(session, plan, payload.items)
        return serialize_plans(session, [plan])[0]
    except IntegrityError as exc:
        raise_plan_integrity_error(exc)


def update_plan(session: Session, plan_id: int, payload: ProductionPlanUpdate) -> dict:
    try:
        plan = load_plan(session, plan_id, for_update=True)
        ensure_revision(plan, payload.expected_revision)
        if plan.status not in {"draft", "cancelled"}:
            raise DomainError(
                "production_plan_not_editable",
                "只有草稿或已取消计划允许修改",
                status_code=409,
            )
        ensure_plan_without_movements(session, plan.id)
        validate_plan_products(session, payload, plan)
        # Remove old customer-bound details before changing the plan customer.
        session.execute(
            delete(DepartmentWorkOrder).where(DepartmentWorkOrder.production_plan_id == plan.id)
        )
        session.flush()
        session.execute(
            delete(ProductionPlanItem).where(ProductionPlanItem.production_plan_id == plan.id)
        )
        for field, value in payload.model_dump(exclude={"expected_revision", "items"}).items():
            setattr(plan, field, value)
        plan.status = "draft"
        plan.confirmed_at = None
        plan.confirmed_by = None
        plan.revision += 1
        plan.updated_at = utc_now()
        session.flush()
        create_plan_items(session, plan, payload.items)
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
    session: Session,
    plan_id: int,
    action: str,
    expected_revision: int,
    actor_username: str,
) -> dict:
    plan = load_plan(session, plan_id, for_update=True)
    ensure_revision(plan, expected_revision)
    if action == "cancel":
        if plan.status not in {"draft", "confirmed"}:
            raise DomainError("production_plan_invalid_status", "当前计划不能取消", status_code=409)
        target = "cancelled"
    else:
        transition = TRANSITIONS.get(action)
        if transition is None or plan.status != transition[0]:
            raise DomainError(
                "production_plan_invalid_status", "当前计划不允许此操作", status_code=409
            )
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


def delete_plan(session: Session, plan_id: int, expected_revision: int) -> None:
    plan = load_plan(session, plan_id, for_update=True)
    ensure_revision(plan, expected_revision)
    if plan.status not in {"draft", "cancelled"}:
        raise DomainError(
            "production_plan_not_deletable",
            "只有草稿或已取消计划允许删除",
            status_code=409,
        )
    ensure_plan_without_movements(session, plan.id)
    session.delete(plan)
