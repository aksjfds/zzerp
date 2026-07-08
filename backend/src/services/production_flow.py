from dataclasses import dataclass

from sqlalchemy import select

from models.engineering import ProductBom, ProductProcessFlow
from models.production import ProductionItem
from models.sales import CustomerOrderItem
from services.errors import DomainError


@dataclass(frozen=True)
class ProductionFlowContext:
    order_item: CustomerOrderItem
    bom_item: ProductBom | None
    flow: dict
    nodes: dict[str, dict]

    def node(self, node_id: str) -> dict:
        node = self.nodes.get(node_id)
        if node is None:
            raise DomainError("flow_node_missing", "当前流程节点不存在")
        return node

    def normal_target(self, node_id: str) -> dict | None:
        return normal_target(self.flow, self.nodes, node_id)

    def item_name(self, production_item: ProductionItem) -> tuple[str, str]:
        if self.bom_item is not None:
            return self.bom_item.part_no, self.bom_item.part_name
        origin = self.nodes.get(production_item.origin_flow_node_id, {})
        name = origin.get("output_name") or origin.get("label") or "装配体"
        return name, name


def load_product_flow(session, product_id: int, product_version: int) -> tuple[dict, dict[str, dict]]:
    cache = session.info.setdefault("product_process_flow_cache", {})
    key = (product_id, product_version)
    if key not in cache:
        cache[key] = session.scalar(
            select(ProductProcessFlow).where(
                ProductProcessFlow.product_id == product_id,
                ProductProcessFlow.product_version == product_version,
            )
        )
    record = cache[key]
    if record is None:
        raise DomainError("production_context_missing", "生产资料不完整")
    flow = record.flow_json
    return flow, {item["id"]: item for item in flow.get("nodes", [])}


def normal_target(flow: dict, nodes: dict[str, dict], node_id: str) -> dict | None:
    targets = [
        nodes.get(edge.get("target_node_id"))
        for edge in flow.get("edges", [])
        if edge.get("source_node_id") == node_id
        and edge.get("route_type", "normal") == "normal"
    ]
    targets = [item for item in targets if item is not None]
    if len(targets) > 1:
        raise DomainError("ambiguous_flow_target", "当前节点存在多个普通出口")
    return targets[0] if targets else None


def load_production_flow(session, production_item: ProductionItem) -> ProductionFlowContext:
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    if order_item is None:
        raise DomainError("production_context_missing", "生产订单明细不存在")
    bom_item = session.get(ProductBom, production_item.product_bom_id) if production_item.product_bom_id else None
    flow, nodes = load_product_flow(session, order_item.product_id, order_item.product_version)
    return ProductionFlowContext(order_item, bom_item, flow, nodes)
