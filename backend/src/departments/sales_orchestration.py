"""Application entry points for customer-order and production-plan workflows."""

from modules.engineering import product_reference_api as engineering
from modules.planning import sales_api as planning
from modules.planning import plan_api as planning_commands
from modules.inventory.plan_stock_api import (
    release_finished_plan_stock,
    reserve_finished_plan_stock,
)
from modules.inventory.finished_shipment_api import order_item_shipped_quantities
from modules.inventory.warehouse_api import withdraw_c01_stock
from modules.inventory.plan_correction_api import (
    ensure_no_completed_plan_storage,
    ensure_order_has_no_shipments,
    reverse_plan_warehouse_issues,
)
from modules.production_core import api as production_lifecycle
from modules.production_core.inventory_api import (
    accept_issued_inventory as accept_inventory_into_production,
)
from modules.planning import sales_progress_api as planning_progress
from modules.sales import command_api as sales


class SalesProductionAdapter:
    cancel_order_production = staticmethod(production_lifecycle.cancel_order_production)


production = SalesProductionAdapter()


class SalesInventoryAdapter:
    order_item_shipped_quantities = staticmethod(order_item_shipped_quantities)


inventory = SalesInventoryAdapter()


class PlanningExecutionAdapter:
    withdraw_warehouse_stock = staticmethod(withdraw_c01_stock)
    reserve_finished_plan_stock = staticmethod(reserve_finished_plan_stock)
    release_finished_plan_stock = staticmethod(release_finished_plan_stock)
    initialize_order_production = staticmethod(
        production_lifecycle.initialize_order_production
    )
    rollback_unstarted_order_production = staticmethod(
        production_lifecycle.rollback_unstarted_order_production
    )
    ensure_order_has_no_shipments = staticmethod(ensure_order_has_no_shipments)
    reverse_plan_warehouse_issues = staticmethod(reverse_plan_warehouse_issues)
    ensure_no_completed_plan_storage = staticmethod(ensure_no_completed_plan_storage)

    @staticmethod
    def accept_issued_inventory(session, plan_item, stock, actor_username):
        return accept_inventory_into_production(
            session,
            plan_item,
            stock,
            actor_username,
        )


plan_execution = PlanningExecutionAdapter()


class SalesPlanningAdapter:
    order_plan_states = staticmethod(planning.order_plan_states)
    order_plan_state = staticmethod(planning.order_plan_state)
    order_progress_by_order_item = staticmethod(
        planning_progress.order_progress_by_order_item
    )
    delete_order_plan = staticmethod(planning.delete_order_plan)
    rebuild_order_plan = staticmethod(planning.rebuild_order_plan)

    @staticmethod
    def confirm_order_plan(session, order, **kwargs):
        return planning_commands.confirm_order_plan(
            session, order, collaborators=plan_execution, **kwargs
        )

    @staticmethod
    def cancel_order_plan(session, order, actor_username):
        return planning_commands.cancel_order_plan(
            session,
            order,
            actor_username,
            collaborators=plan_execution,
        )

    @staticmethod
    def unconfirm_order_plan(session, order, **kwargs):
        return planning_commands.unconfirm_order_plan(
            session, order, collaborators=plan_execution, **kwargs
        )

    @staticmethod
    def reopen_completed_order_plan(session, order, **kwargs):
        return planning_commands.reopen_completed_order_plan(
            session, order, collaborators=plan_execution, **kwargs
        )


planning_port = SalesPlanningAdapter()


def list_orders(page: int, page_size: int, **kwargs) -> tuple[list[dict], int]:
    return sales.list_orders(
        page,
        page_size,
        planning=planning_port,
        engineering=engineering,
        **kwargs,
    )


def list_order_progress_details(
    page: int,
    page_size: int,
    customer_id: int | None = None,
) -> tuple[list[dict], int]:
    return sales.list_order_progress_details(
        page,
        page_size,
        customer_id,
        planning=planning_port,
        engineering=engineering,
        inventory=inventory,
    )


def get_order(order_id: int) -> dict:
    return sales.get_order(order_id, planning_port, engineering)


def update_order(order_id: int, payload) -> dict:
    return sales.update_order(
        order_id,
        payload,
        planning_port,
        engineering,
    )


def change_status(*args, **kwargs) -> dict:
    return sales.change_status(
        *args,
        planning=planning_port,
        engineering=engineering,
        production=production,
        **kwargs,
    )


def confirm_production_plan(*args, **kwargs) -> dict:
    return sales.confirm_production_plan(
        *args,
        planning=planning_port,
        engineering=engineering,
        **kwargs,
    )


def unconfirm_production_plan(*args, **kwargs) -> dict:
    return sales.unconfirm_production_plan(
        *args,
        planning=planning_port,
        engineering=engineering,
        **kwargs,
    )


def reopen_completed_production_plan(*args, **kwargs) -> dict:
    return sales.reopen_completed_production_plan(
        *args,
        planning=planning_port,
        engineering=engineering,
        **kwargs,
    )


def create_order(payload) -> dict:
    return sales.create_order(payload, engineering)


delete_order = sales.delete_order
get_customer_order_production = planning_progress.get_customer_order_production


__all__ = [
    "change_status",
    "confirm_production_plan",
    "create_order",
    "delete_order",
    "get_order",
    "get_customer_order_production",
    "list_order_progress_details",
    "list_orders",
    "reopen_completed_production_plan",
    "unconfirm_production_plan",
    "update_order",
]
