"""Cross-domain read model for production-plan inventory outbound work."""

from sqlalchemy import select

from database import SessionLocal
from modules.engineering.model_api import ProductBom
from modules.inventory.model_api import InventoryReservation, InventoryStock
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.production_core.flow_api import (
    completed_node_display_label,
    load_product_flow,
)
from modules.sales.model_api import CustomerOrder


def list_outbound_plans(department_code: str) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(
                ProductionPlan,
                CustomerOrder,
                InventoryReservation,
                InventoryStock,
                ProductionPlanItem,
                ProductBom,
            )
            .join(CustomerOrder, CustomerOrder.id == ProductionPlan.customer_order_id)
            .join(
                InventoryReservation,
                InventoryReservation.production_plan_id == ProductionPlan.id,
            )
            .join(
                InventoryStock,
                InventoryStock.id == InventoryReservation.inventory_stock_id,
            )
            .join(
                ProductionPlanItem,
                ProductionPlanItem.id
                == InventoryReservation.production_plan_item_id,
            )
            .outerjoin(ProductBom, ProductBom.id == ProductionPlanItem.product_bom_id)
            .where(
                ProductionPlan.status == "confirmed",
                InventoryStock.department_code == department_code,
                InventoryReservation.status.in_(("reserved", "issued")),
                InventoryReservation.issued_quantity
                < InventoryReservation.reserved_quantity,
            )
            .order_by(ProductionPlan.id, InventoryReservation.id)
        )
        context_rows = list(rows)
        flow_contexts = {
            key: load_product_flow(session, *key)
            for key in {
                (stock.product_id, stock.product_version)
                for _plan, _order, _reservation, stock, _item, _bom in context_rows
            }
        }
        plans: dict[int, dict] = {}
        for plan, order, reservation, stock, item, bom_item in context_rows:
            item_name = item.item_name
            if item.item_type == "part" and bom_item is not None:
                item_name = bom_item.part_name
            flow, nodes = flow_contexts[(stock.product_id, stock.product_version)]
            entry = plans.setdefault(
                plan.id,
                {
                    "production_plan_id": plan.id,
                    "customer_order_id": order.id,
                    "customer_order_no": order.customer_order_no,
                    "department_code": department_code,
                    "items": [],
                },
            )
            entry["items"].append({
                "reservation_id": reservation.id,
                "item_code": item.item_code,
                "item_name": item_name,
                "reserved_quantity": reservation.reserved_quantity,
                "issued_quantity": reservation.issued_quantity,
                "remaining_quantity": (
                    reservation.reserved_quantity - reservation.issued_quantity
                ),
                "completed_node_label": completed_node_display_label(
                    flow,
                    nodes,
                    stock.flow_node_id,
                    stock.completed_flow_node_id,
                ),
            })
        return list(plans.values())


__all__ = ["list_outbound_plans"]
