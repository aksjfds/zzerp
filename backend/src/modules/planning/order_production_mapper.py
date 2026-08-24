from __future__ import annotations

"""Customer-order production response mapping."""

from modules.sales.model_api import CustomerOrderItem
from modules.production_core.flow_api import load_product_flow
from modules.planning.order_production_calculations import _calculate_order_item_state
from modules.planning.order_production_context import OrderProductionReadContext

def _serialize_order_item(
    context: OrderProductionReadContext,
    order_item: CustomerOrderItem,
) -> dict:
    product = context.products[order_item.product_id]
    flow, nodes = load_product_flow(
        context.session,
        order_item.product_id,
        order_item.product_version,
        context.display.flow_cache,
    )
    state = _calculate_order_item_state(context, order_item, flow, nodes)
    return {
        "customer_order_item_id": order_item.id,
        "product_name": product.product_name,
        "factory_code": product.factory_code,
        "product_version": order_item.product_version,
        "order_quantity": order_item.quantity,
        "process_flow": flow,
        **state,
    }
