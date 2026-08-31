from __future__ import annotations

"""Production-plan commands and transaction boundaries."""

from sqlalchemy.orm import Session
from database import SessionLocal
from domain.time import utc_now
from modules.errors import DomainError
from modules.planning.execution_contract import PlanExecutionCollaborators
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.plan_confirmation import allocate_plan_inventory
from modules.planning.plan_builder import planned_finished_quantity, refresh_plan_availability
from modules.planning.route_projection import rebuild_plan_route_tasks
from modules.planning.plan_access import _ensure_revision, _load_plan
from modules.planning.plan_mapper import serialize_plan
from modules.planning.plan_validation import _validate_product_output

def get_order_plan(order_id: int) -> dict:
    with SessionLocal() as session:
        plan = _load_plan(session, order_id)
        if plan is None:
            raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
        if plan.status == "draft":
            refresh_plan_availability(session, plan)
        return serialize_plan(session, plan)

def update_order_plan(
    order_id: int,
    expected_revision: int,
    quantity_items: list[tuple[int, int]],
) -> dict:
    quantities = dict(quantity_items)
    if len(quantities) != len(quantity_items):
        raise DomainError(
            "duplicate_production_plan_item",
            "生产计划项目不能重复",
            path="items",
        )
    with SessionLocal.begin() as session:
        plan = _load_plan(session, order_id, for_update=True)
        if plan is None:
            raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
        if plan.status != "draft":
            raise DomainError("production_plan_not_editable", "只有未确认生产计划允许修改")
        _ensure_revision(plan, expected_revision)
        refresh_plan_availability(session, plan)
        editable_items = [item for item in plan.items if item.item_type == "part"]
        expected_ids = {item.id for item in editable_items}
        if set(quantities) != expected_ids:
            raise DomainError(
                "production_plan_items_incomplete",
                "必须提交生产计划中的全部普通配件",
                path="items",
            )
        for item in editable_items:
            quantity = quantities[item.id]
            item.planned_production_quantity = quantity
        _validate_product_output(session, plan.items)
        plan.revision += 1
        plan.updated_at = utc_now()
        session.flush()
        rebuild_plan_route_tasks(session, plan)
        return serialize_plan(session, plan)

def confirm_order_plan(
    session: Session,
    order,
    *,
    expected_revision: int,
    actor_username: str,
    collaborators: PlanExecutionCollaborators,
) -> ProductionPlan:
    plan = _load_plan(session, order.id, for_update=True)
    if plan is None:
        raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
    if plan.status != "draft":
        raise DomainError("production_plan_not_confirmable", "当前生产计划不能确认")
    _ensure_revision(plan, expected_revision)
    refresh_plan_availability(session, plan)
    groups: dict[int, list[ProductionPlanItem]] = {}
    for item in plan.items:
        groups.setdefault(item.customer_order_item_id, []).append(item)
    for items in groups.values():
        finished = next(item for item in items if item.item_type == "finished_product")
        supported_quantity = planned_finished_quantity(session, items)
        if supported_quantity < finished.gross_required_quantity:
            raise DomainError(
                "planned_quantity_insufficient",
                f"{finished.item_code} {finished.item_name}按 BOM 最多可满足 "
                f"{supported_quantity} 件，少于订单需求 {finished.gross_required_quantity} 件",
                path="items",
            )
    issued_rows = allocate_plan_inventory(
        session,
        plan,
        actor_username,
        collaborators,
    )
    part_quantities = {
        (item.customer_order_item_id, item.product_bom_id, item.flow_node_id):
            item.planned_production_quantity
        for item in plan.items
        if item.item_type == "part" and item.product_bom_id is not None
    }
    collaborators.initialize_order_production(session, order, part_quantities=part_quantities)
    for plan_item, stock in issued_rows:
        collaborators.accept_issued_inventory(
            session,
            plan_item,
            stock,
            actor_username,
        )
    plan.status = "confirmed"
    plan.confirmed_at = utc_now()
    plan.confirmed_by = actor_username
    plan.updated_at = utc_now()
    plan.revision += 1
    return plan

def cancel_order_plan(
    session: Session,
    order,
    _actor_username: str,
    *,
    collaborators: PlanExecutionCollaborators,
) -> None:
    plan = _load_plan(session, order.id, for_update=True)
    if plan is None:
        return
    if plan.status == "cancelled":
        return
    if plan.status == "completed":
        raise DomainError(
            "production_plan_completed",
            "已完成的生产计划不能取消",
            status_code=409,
        )
    if plan.status == "confirmed":
        if any(
            item.item_type != "finished_product"
            and item.allocated_inventory_quantity > 0
            for item in plan.items
        ):
            raise DomainError(
                "production_plan_material_issued",
                "生产计划已经从仓库实际出库，不能取消",
                status_code=409,
            )
        collaborators.release_finished_plan_stock(session, plan.id)
    plan.status = "cancelled"
    plan.updated_at = utc_now()
    plan.revision += 1

def complete_order_plan(
    order_id: int,
    expected_revision: int,
    actor_username: str,
) -> dict:
    with SessionLocal.begin() as session:
        plan = _load_plan(session, order_id, for_update=True)
        if plan is None:
            raise DomainError("production_plan_not_found", "生产计划不存在", status_code=404)
        if plan.status != "confirmed":
            raise DomainError(
                "production_plan_not_completable",
                "只有生产中的计划可以完成",
                status_code=409,
            )
        _ensure_revision(plan, expected_revision)
        plan.status = "completed"
        plan.completed_at = utc_now()
        plan.completed_by = actor_username
        plan.updated_at = utc_now()
        plan.revision += 1
        session.flush()
        return serialize_plan(session, plan)
