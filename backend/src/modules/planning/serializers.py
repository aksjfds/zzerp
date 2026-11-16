from domain.time import business_iso
from sqlalchemy import select
from sqlalchemy.orm import load_only

from modules.planning.persistence import ProductionPlanItem
from modules.sales.customer_api import customer_names_by_ids


def serialize_plans(session, plans) -> list[dict]:
    if not plans:
        return []
    items = list(session.scalars(select(ProductionPlanItem).options(load_only(
            ProductionPlanItem.production_plan_id, ProductionPlanItem.product_id,
            ProductionPlanItem.product_name, ProductionPlanItem.factory_code, ProductionPlanItem.customer_code,
            ProductionPlanItem.source_version, ProductionPlanItem.source_version_value, ProductionPlanItem.order_quantity, ProductionPlanItem.production_quantity))
        .where(ProductionPlanItem.production_plan_id.in_({plan.id for plan in plans}))
        .order_by(ProductionPlanItem.product_id)))
    by_plan = {}
    for item in items:
        product = item
        by_plan.setdefault(item.production_plan_id, []).append({
            "product_id": item.product_id, "product_name": product.product_name,
            "factory_code": product.factory_code, "source_version": item.source_version,
            "source_version_value": item.source_version_value,
            "customer_code": item.customer_code, "order_quantity": item.order_quantity,
            "production_quantity": item.production_quantity,
        })
    customers = customer_names_by_ids(session, {plan.customer_id for plan in plans})
    return [
        {
            "id": plan.id,
            "customer_id": plan.customer_id,
            "customer_name": customers[plan.customer_id],
            "order_no": plan.order_no,
            "items": by_plan.get(plan.id, []),
            "status": plan.status,
            "revision": plan.revision,
            "confirmed_at": business_iso(plan.confirmed_at),
            "confirmed_by": plan.confirmed_by,
            "completed_at": business_iso(plan.completed_at),
            "completed_by": plan.completed_by,
            "created_at": business_iso(plan.created_at),
            "updated_at": business_iso(plan.updated_at),
        }
        for plan in plans
    ]
