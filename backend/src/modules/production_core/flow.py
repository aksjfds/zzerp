from dataclasses import dataclass

from sqlalchemy import select

from modules.engineering.model_api import ProductBom, ProductProcessFlow
from modules.production_core.persistence import ProductionItem
from modules.sales.model_api import CustomerOrderItem
from modules.errors import DomainError


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


def load_product_flow(
    session,
    product_id: int,
    product_version: int,
    flow_cache: dict[tuple[int, int], ProductProcessFlow] | None = None,
) -> tuple[dict, dict[str, dict]]:
    key = (product_id, product_version)
    if flow_cache is not None and key in flow_cache:
        record = flow_cache[key]
    else:
        record = session.scalar(
            select(ProductProcessFlow).where(
                ProductProcessFlow.product_id == product_id,
                ProductProcessFlow.product_version == product_version,
            )
        )
        if flow_cache is not None and record is not None:
            flow_cache[key] = record
    if record is None:
        raise DomainError("production_context_missing", "生产资料不完整")
    flow = record.flow_json
    return flow, {item["id"]: item for item in flow.get("nodes", [])}


def normal_target(flow: dict, nodes: dict[str, dict], node_id: str) -> dict | None:
    targets = [
        nodes.get(edge.get("target_node_id"))
        for edge in flow.get("edges", [])
        if edge.get("source_node_id") == node_id
    ]
    targets = [item for item in targets if item is not None]
    if len(targets) > 1:
        raise DomainError("ambiguous_flow_target", "当前节点存在多个普通出口")
    return targets[0] if targets else None


def physical_route_nodes(
    flow: dict,
    nodes: dict[str, dict],
    origin_node_id: str,
) -> list[dict]:
    """Return every downstream physical route until the next assembly or inbound node."""
    origin = nodes.get(origin_node_id)
    if origin is None:
        return []
    origin_is_assembly = origin.get("type") == "assembly"
    route = [origin] if origin_is_assembly else []
    visited = {origin_node_id}
    queue = _ordered_targets(flow, nodes, origin_node_id)
    while queue:
        node = queue.pop(0)
        node_id = node["id"]
        if node_id in visited:
            continue
        visited.add(node_id)
        if node.get("type") == "assembly":
            if not origin_is_assembly:
                route.append(node)
            continue
        route.append(node)
        if node.get("type") != "finished_inbound":
            queue.extend(_ordered_targets(flow, nodes, node_id))
    return route


def _ordered_targets(
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> list[dict]:
    targets = {
        target["id"]: target
        for edge in flow.get("edges", [])
        if edge.get("source_node_id") == node_id
        for target in [nodes.get(edge.get("target_node_id"))]
        if target is not None
    }
    return sorted(
        targets.values(),
        key=lambda item: (
            float(item.get("x") or 0),
            float(item.get("y") or 0),
            item["id"],
        ),
    )


def assembly_material_key(
    flow: dict,
    nodes: dict[str, dict],
    source_node_id: str,
) -> str | None:
    """Resolve a route endpoint to the logical BOM/assembly material it carries."""
    current_id = source_node_id
    visited: set[str] = set()
    while current_id not in visited:
        visited.add(current_id)
        node = nodes.get(current_id)
        if node is None:
            return None
        if node.get("type") == "part":
            bom_item_id = node.get("bom_item_id")
            return f"part:{bom_item_id}" if bom_item_id is not None else None
        if node.get("type") == "assembly":
            return f"assembly:{node['id']}"
        sources = [
            edge.get("source_node_id")
            for edge in flow.get("edges", [])
            if edge.get("target_node_id") == current_id
            and edge.get("source_node_id")
        ]
        if len(sources) != 1:
            return None
        current_id = sources[0]
    return None


def process_qc_node(
    flow: dict,
    nodes: dict[str, dict],
    process_node_id: str,
) -> dict | None:
    target = normal_target(flow, nodes, process_node_id)
    return target if target and target.get("type") == "qc" else None


def qc_qualified_destinations(
    flow: dict,
    nodes: dict[str, dict],
    process_node_id: str,
) -> tuple[str, ...]:
    """Return server-authoritative destinations for qualified material."""
    target = qc_release_target(flow, nodes, process_node_id)
    destinations = ["return"]
    if target is not None:
        destinations.append("release")
    if target is None or target.get("type") != "finished_inbound":
        destinations.append("inventory")
    return tuple(destinations)


def qc_release_target(
    flow: dict,
    nodes: dict[str, dict],
    process_node_id: str,
) -> dict | None:
    """Resolve the release target for configured or ad-hoc QC."""
    qc_node = process_qc_node(flow, nodes, process_node_id)
    return normal_target(
        flow,
        nodes,
        qc_node["id"] if qc_node is not None else process_node_id,
    )


def next_execution_node(
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> dict | None:
    target = normal_target(flow, nodes, node_id)
    if target and target.get("type") == "qc":
        return normal_target(flow, nodes, target["id"])
    return target


def load_production_flow(
    session,
    production_item: ProductionItem,
    *,
    flow_cache: dict[tuple[int, int], ProductProcessFlow] | None = None,
    order_items: dict[int, CustomerOrderItem] | None = None,
    bom_items: dict[int, ProductBom] | None = None,
) -> ProductionFlowContext:
    order_item = (
        order_items.get(production_item.customer_order_item_id)
        if order_items is not None else None
    ) or session.get(
            CustomerOrderItem,
            production_item.customer_order_item_id,
        )
    if order_item is None:
        raise DomainError("production_context_missing", "生产订单明细不存在")
    bom_item = None
    if production_item.product_bom_id is not None:
        bom_item = (
            bom_items.get(production_item.product_bom_id)
            if bom_items is not None else None
        ) or session.get(ProductBom, production_item.product_bom_id)
    flow, nodes = load_product_flow(
        session,
        order_item.product_id,
        order_item.product_version,
        flow_cache,
    )
    return ProductionFlowContext(order_item, bom_item, flow, nodes)
