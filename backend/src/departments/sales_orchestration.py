"""Application entry points for customer-order and production-plan workflows."""

from modules.engineering import product_reference_api as engineering
from modules.planning import sales_api as planning
from modules.planning import plan_api as planning_commands
from modules.inventory.finished_goods_api import (
    allocate_issued_finished_goods,
    register_pending_finished_goods,
)
from modules.inventory.plan_stock_api import withdraw_finished_plan_stock
from modules.inventory.warehouse_api import withdraw_c01_stock
from modules.production_core import api as production_lifecycle
from modules.production_core.inventory_api import (
    accept_issued_inventory as accept_inventory_into_production,
)
from modules.production_core import operational_api as production_operations
from modules.planning import sales_progress_api as planning_progress
from modules.sales import command_api as sales


class SalesProductionAdapter:
    order_item_shipped_quantities = staticmethod(
        planning_progress.order_item_shipped_quantities
    )
    load_product_flow = staticmethod(production_operations.load_product_flow)
    shipping_node_and_unit_quantity = staticmethod(
        production_operations.shipping_node_and_unit_quantity
    )


production = SalesProductionAdapter()


class PlanningExecutionAdapter:
    withdraw_warehouse_stock = staticmethod(withdraw_c01_stock)
    withdraw_finished_plan_stock = staticmethod(withdraw_finished_plan_stock)
    initialize_order_production = staticmethod(
        production_lifecycle.initialize_order_production
    )

    @staticmethod
    def accept_issued_inventory(session, plan_item, stock, actor_username):
        return accept_inventory_into_production(
            session,
            plan_item,
            stock,
            actor_username,
            register_pending_finished_goods=register_pending_finished_goods,
            allocate_issued_finished_goods=allocate_issued_finished_goods,
        )


plan_execution = PlanningExecutionAdapter()


class SalesPlanningAdapter:
    order_plan_states = staticmethod(planning.order_plan_states)
    order_plan_state = staticmethod(planning.order_plan_state)
    planned_product_quantities = staticmethod(planning.planned_product_quantities)
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
            session, order, actor_username
        )


planning_port = SalesPlanningAdapter()


def list_orders(page: int, page_size: int, **kwargs) -> tuple[list[dict], int]:
    return sales.list_orders(
        page,
        page_size,
        planning=planning_port,
        engineering=engineering,
        production=production,
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
        production=production,
    )


def get_order(order_id: int) -> dict:
    return sales.get_order(order_id, planning_port, engineering, production)


def update_order(order_id: int, payload) -> dict:
    return sales.update_order(
        order_id,
        payload,
        planning_port,
        engineering,
        production,
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
        production=production,
        **kwargs,
    )


def create_order(payload) -> dict:
    return sales.create_order(payload, engineering, production)


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
    "update_order",
]
