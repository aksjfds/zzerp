from domain.time import business_iso
from modules.engineering.product_reference_api import get_product_references
from modules.sales.customer_api import customer_names_by_ids


def serialize_plans(session, plans) -> list[dict]:
    products = get_product_references(session, {plan.product_id for plan in plans})
    customers = customer_names_by_ids(session, {plan.customer_id for plan in plans})
    return [
        {
            "id": plan.id,
            "customer_id": plan.customer_id,
            "customer_name": customers[plan.customer_id],
            "order_no": plan.order_no,
            "order_quantity": plan.order_quantity,
            "product_id": plan.product_id,
            "product_name": products[plan.product_id].product_name,
            "factory_code": products[plan.product_id].factory_code,
            "production_quantity": plan.production_quantity,
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
