"""Planning-owned update applied during inventory issue orchestration."""

from domain.production_inventory import IssuedPlanItem
from modules.errors import DomainError
from modules.planning.persistence import ProductionPlanItem


def apply_issued_plan_quantity(
    session,
    production_plan_item_id: int,
    quantity: int,
) -> IssuedPlanItem:
    item = session.get(
        ProductionPlanItem,
        production_plan_item_id,
        with_for_update=True,
    )
    if item is None:
        raise DomainError(
            "production_plan_item_not_found",
            "生产计划项目不存在",
            status_code=409,
        )
    item.issued_inventory_quantity += quantity
    return IssuedPlanItem(
        id=item.id,
        customer_order_item_id=item.customer_order_item_id,
        product_id=item.product_id,
        product_version=item.product_version,
        item_type=item.item_type,
        product_bom_id=item.product_bom_id,
        flow_node_id=item.flow_node_id,
    )


__all__ = ["apply_issued_plan_quantity"]
