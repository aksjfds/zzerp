from __future__ import annotations

"""Production-plan response and inventory-view mapping."""

from sqlalchemy.orm import Session
from domain.time import business_iso
from modules.planning.persistence import ProductionPlan, ProductionPlanItem
from modules.planning.plan_builder import planned_product_quantity
from modules.planning.plan_inventory_view import _serialize_inventory_items

def serialize_plan(session: Session, plan: ProductionPlan) -> dict:
    groups: dict[int, list[ProductionPlanItem]] = {}
    for item in plan.items:
        groups.setdefault(item.customer_order_item_id, []).append(item)
    return {
        "id": plan.id,
        "customer_order_id": plan.customer_order_id,
        "status": plan.status,
        "revision": plan.revision,
        "product_summaries": [
            {
                "customer_order_item_id": customer_order_item_id,
                "product_id": finished.product_id,
                "product_version": finished.product_version,
                "product_code": finished.item_code,
                "product_name": finished.item_name,
                "order_quantity": finished.gross_required_quantity,
                "planned_finished_quantity": planned_product_quantity(items),
            }
            for customer_order_item_id, items in groups.items()
            for finished in [next(item for item in items if item.item_type == "finished_product")]
        ],
        "items": [
            {
                "id": item.id,
                "customer_order_item_id": item.customer_order_item_id,
                "item_type": item.item_type,
                "product_id": item.product_id,
                "product_version": item.product_version,
                "product_bom_id": item.product_bom_id,
                "flow_node_id": item.flow_node_id,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "unit_requirement": item.unit_requirement,
                "gross_required_quantity": item.gross_required_quantity,
                "estimated_inventory_quantity": item.estimated_inventory_quantity,
                "net_required_quantity": item.net_required_quantity,
                "planned_production_quantity": item.planned_production_quantity,
                "reserved_inventory_quantity": item.reserved_inventory_quantity,
                "issued_inventory_quantity": item.issued_inventory_quantity,
                "available_inventory_quantity": max(
                    item.estimated_inventory_quantity - item.reserved_inventory_quantity,
                    0,
                ) if plan.status != "draft" else item.estimated_inventory_quantity,
            }
            for item in plan.items
            if item.item_type == "part"
        ],
        "inventory_items": _serialize_inventory_items(session, plan),
        "confirmed_at": business_iso(plan.confirmed_at),
        "confirmed_by": plan.confirmed_by,
        "completed_at": business_iso(plan.completed_at),
        "completed_by": plan.completed_by,
        "created_at": business_iso(plan.created_at),
        "updated_at": business_iso(plan.updated_at),
    }

