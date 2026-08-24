"""Persist formal engineering routes for database-side department queries."""

from collections import defaultdict, deque

from sqlalchemy import delete
from sqlalchemy.orm import Session

from modules.engineering.persistence import ProductRouteTask


def rebuild_product_route_tasks(
    session: Session,
    *,
    product_id: int,
    product_version: int,
    flow_json: dict,
) -> None:
    session.execute(delete(ProductRouteTask).where(
        ProductRouteTask.product_id == product_id,
        ProductRouteTask.product_version == product_version,
    ))
    nodes = {
        str(node["id"]): node
        for node in flow_json.get("nodes", [])
        if node.get("id")
    }
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in flow_json.get("edges", []):
        source = str(edge.get("source_node_id") or "")
        target = str(edge.get("target_node_id") or "")
        if source in nodes and target in nodes:
            outgoing[source].append(target)
    for targets in outgoing.values():
        targets.sort(key=lambda node_id: _node_order(nodes[node_id]))

    for origin in nodes.values():
        if origin.get("type") not in {"part", "assembly"}:
            continue
        for route_order, node in enumerate(_execution_route(origin, nodes, outgoing)):
            workshop_id = node.get("workshop_id")
            if node.get("type") not in {"process", "assembly"} or not isinstance(workshop_id, int):
                continue
            session.add(ProductRouteTask(
                product_id=product_id,
                product_version=product_version,
                product_bom_id=(origin.get("bom_item_id") if origin.get("type") == "part" else None),
                origin_flow_node_id=str(origin["id"]),
                origin_node_type=str(origin["type"]),
                origin_item_code=str(
                    origin.get("part_no")
                    or origin.get("assembly_code")
                    or origin.get("output_name")
                    or origin.get("label")
                    or origin["id"]
                ),
                origin_item_name=str(
                    origin.get("part_name")
                    or origin.get("output_name")
                    or origin.get("label")
                    or "装配体"
                ),
                route_flow_node_id=str(node["id"]),
                route_node_type=str(node["type"]),
                workshop_id=workshop_id,
                route_order=route_order,
            ))


def _execution_route(
    origin: dict,
    nodes: dict[str, dict],
    outgoing: dict[str, list[str]],
) -> list[dict]:
    origin_id = str(origin["id"])
    origin_is_assembly = origin.get("type") == "assembly"
    result = [origin] if origin_is_assembly else []
    queue = deque(outgoing.get(origin_id, ()))
    visited = {origin_id}
    while queue:
        node_id = queue.popleft()
        if node_id in visited:
            continue
        visited.add(node_id)
        node = nodes[node_id]
        if node.get("type") == "assembly":
            if not origin_is_assembly:
                result.append(node)
            continue
        result.append(node)
        if node.get("type") != "shipping":
            queue.extend(outgoing.get(node_id, ()))
    return result


def _node_order(node: dict) -> tuple[float, float, str]:
    return float(node.get("x") or 0), float(node.get("y") or 0), str(node["id"])


__all__ = ["rebuild_product_route_tasks"]
