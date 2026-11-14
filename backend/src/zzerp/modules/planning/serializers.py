from sqlalchemy import select

from zzerp.modules.engineering.api import appearance_names, get_product_references
from zzerp.modules.planning.persistence import ProductionPlanItem
from zzerp.modules.sales.api import customer_names_by_ids
from zzerp.time import business_iso


def serialize_plans(session, plans) -> list[dict]:
    if not plans:
        return []
    items = list(
        session.scalars(
            select(ProductionPlanItem)
            .where(ProductionPlanItem.production_plan_id.in_({plan.id for plan in plans}))
            .order_by(ProductionPlanItem.product_id, ProductionPlanItem.appearance_id)
        )
    )
    products = get_product_references(session, {item.product_id for item in items})
    names = appearance_names(session, {item.appearance_id for item in items})
    by_plan = {}
    for item in items:
        product = products[item.product_id]
        by_plan.setdefault(item.production_plan_id, []).append(
            dict(
                product_id=item.product_id,
                appearance_id=item.appearance_id,
                appearance_name=names[item.appearance_id],
                product_name=product.product_name,
                factory_code=product.factory_code,
                order_quantity=item.order_quantity,
                production_quantity=item.production_quantity,
            )
        )
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
