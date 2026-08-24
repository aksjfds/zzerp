"""Application orchestration for issuing reserved plan inventory."""

from database import SessionLocal
from modules.errors import DomainError
from modules.inventory.finished_goods_api import (
    allocate_issued_finished_goods,
    register_pending_finished_goods,
)
from modules.inventory.reservation_api import (
    apply_plan_reservation_issue,
    prepare_plan_reservation_issues,
    record_plan_reservation_issue,
)
from modules.planning.api import list_outbound_plans
from modules.planning.issue_api import apply_issued_plan_quantity
from modules.production_core.inventory_api import accept_issued_inventory


def issue_outbound_plan(
    production_plan_id: int,
    department_code: str,
    quantity_items: list[tuple[int, int]],
    actor_username: str,
) -> dict:
    quantities = dict(quantity_items)
    if len(quantities) != len(quantity_items):
        raise DomainError(
            "duplicate_inventory_reservation",
            "出库项目不能重复",
            path="items",
        )
    with SessionLocal.begin() as session:
        prepared_issues = prepare_plan_reservation_issues(
            session,
            production_plan_id=production_plan_id,
            department_code=department_code,
            quantities=quantities,
            actor_username=actor_username,
        )
        for prepared in prepared_issues:
            issued_stock = apply_plan_reservation_issue(
                session,
                prepared,
                actor_username,
            )
            plan_item = apply_issued_plan_quantity(
                session,
                prepared.production_plan_item_id,
                prepared.quantity,
            )
            accept_issued_inventory(
                session,
                plan_item,
                issued_stock,
                actor_username,
                register_pending_finished_goods=register_pending_finished_goods,
                allocate_issued_finished_goods=allocate_issued_finished_goods,
            )
            record_plan_reservation_issue(
                session,
                issued_stock,
                production_plan_id,
                actor_username,
            )
    return next(
        (
            item
            for item in list_outbound_plans(department_code)
            if item["production_plan_id"] == production_plan_id
        ),
        {
            "production_plan_id": production_plan_id,
            "customer_order_id": 0,
            "customer_order_no": "",
            "department_code": department_code,
            "items": [],
        },
    )


__all__ = ["issue_outbound_plan"]
