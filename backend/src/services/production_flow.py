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
    ]
    targets = [item for item in targets if item is not None]
    if len(targets) > 1:
        raise DomainError("ambiguous_flow_target", "当前节点存在多个普通出口")
    return targets[0] if targets else None


def process_qc_node(
    flow: dict,
    nodes: dict[str, dict],
    process_node_id: str,
) -> dict | None:
    target = normal_target(flow, nodes, process_node_id)
    return target if target and target.get("type") == "qc" else None


def next_execution_node(
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> dict | None:
    target = normal_target(flow, nodes, node_id)
    if target and target.get("type") == "qc":
        return normal_target(flow, nodes, target["id"])
    return target


def part_route_procedure_ids(
    flow: dict,
    bom_item_id: int,
    allowed_procedure_ids: set[int] | None = None,
) -> list[int]:
    nodes = {item["id"]: item for item in flow.get("nodes", [])}
    part = next(
        (
            node
            for node in nodes.values()
            if node.get("type") == "part" and node.get("bom_item_id") == bom_item_id
        ),
        None,
    )
    if part is None:
        return []

    procedure_ids: list[int] = []
    visited: set[str] = set()
    node = normal_target(flow, nodes, part["id"])
    while node is not None and node["id"] not in visited:
        visited.add(node["id"])
        if node.get("type") == "assembly":
            break
        procedure_id = node.get("procedure_id")
        if (
            node.get("type") == "process"
            and isinstance(procedure_id, int)
            and (
                allowed_procedure_ids is None
                or procedure_id in allowed_procedure_ids
            )
            and procedure_id not in procedure_ids
        ):
            procedure_ids.append(procedure_id)
        node = normal_target(flow, nodes, node["id"])
    return procedure_ids


def origin_route_procedure_ids(
    flow: dict,
    origin_node_id: str,
    allowed_procedure_ids: set[int] | None = None,
) -> list[int]:
    """Return procedures applied to one physical item before it is assembled again."""
    nodes = {item["id"]: item for item in flow.get("nodes", [])}
    origin = nodes.get(origin_node_id)
    if origin is None or origin.get("type") not in {"part", "assembly"}:
        return []
    procedure_ids: list[int] = []
    visited: set[str] = set()
    node = normal_target(flow, nodes, origin_node_id)
    while node is not None and node["id"] not in visited:
        visited.add(node["id"])
        if node.get("type") == "assembly":
            break
        procedure_id = node.get("procedure_id")
        if (
            node.get("type") == "process"
            and isinstance(procedure_id, int)
            and (allowed_procedure_ids is None or procedure_id in allowed_procedure_ids)
            and procedure_id not in procedure_ids
        ):
            procedure_ids.append(procedure_id)
        node = normal_target(flow, nodes, node["id"])
    return procedure_ids


def load_production_flow(session, production_item: ProductionItem) -> ProductionFlowContext:
    order_item = session.get(CustomerOrderItem, production_item.customer_order_item_id)
    if order_item is None:
        raise DomainError("production_context_missing", "生产订单明细不存在")
    bom_item = session.get(ProductBom, production_item.product_bom_id) if production_item.product_bom_id else None
    flow, nodes = load_product_flow(session, order_item.product_id, order_item.product_version)
    return ProductionFlowContext(order_item, bom_item, flow, nodes)
