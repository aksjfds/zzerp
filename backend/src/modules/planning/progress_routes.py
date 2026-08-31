"""Canonical physical-route traversal used by planning progress views."""


def progress_route_nodes(
    flow: dict,
    nodes: dict[str, dict],
    origin_node_id: str,
) -> list[dict]:
    route = []
    origin = nodes.get(origin_node_id)
    if origin and origin.get("type") == "assembly":
        route.append(origin)
    current = _normal_target(flow, nodes, origin_node_id)
    visited: set[str] = set()
    while current and current["id"] not in visited:
        visited.add(current["id"])
        route.append(current)
        if current.get("type") in {"assembly", "finished_inbound"}:
            break
        current = _normal_target(flow, nodes, current["id"])
    return route


def _normal_target(
    flow: dict,
    nodes: dict[str, dict],
    node_id: str,
) -> dict | None:
    targets = [
        nodes.get(edge.get("target_node_id"))
        for edge in flow.get("edges", [])
        if edge.get("source_node_id") == node_id
    ]
    targets = [item for item in targets if item is not None]
    return targets[0] if len(targets) == 1 else None


__all__ = ["progress_route_nodes"]
