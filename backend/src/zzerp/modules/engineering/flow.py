"""Graph integrity and department reachability from explicit part origins."""

from dataclasses import dataclass

from zzerp.errors import DomainError


def validate_process_flow(flow):
    node_ids = set()
    part_ids = set()
    for node in flow.nodes:
        if node.id in node_ids:
            raise DomainError(
                "duplicate_flow_node", "节点 ID 不能重复", "process_flow.nodes", node.id
            )
        node_ids.add(node.id)
        if node.type == "part":
            if node.bom_item_id in part_ids:
                raise DomainError(
                    "duplicate_part_node",
                    "同一配件只能有一个起点节点",
                    "process_flow.nodes",
                    node.id,
                )
            part_ids.add(node.bom_item_id)
    nodes = {node.id: node for node in flow.nodes}
    edge_ids = set()
    for edge in flow.edges:
        if edge.id in edge_ids or edge.id in node_ids:
            raise DomainError(
                "duplicate_flow_edge", "连线 ID 不能重复", "process_flow.edges", edge.id
            )
        edge_ids.add(edge.id)
        if edge.source_node_id not in nodes or edge.target_node_id not in nodes:
            raise DomainError(
                "flow_endpoint_missing", "连线必须引用存在的节点", "process_flow.edges", edge.id
            )
        if nodes[edge.target_node_id].type == "part":
            raise DomainError(
                "part_node_is_origin",
                "配件节点是路线起点，不能连接输入线",
                "process_flow.edges",
                edge.id,
            )
    return flow


def reachable_department_pairs(flow) -> list[tuple[str, str]]:
    validate_process_flow(flow)
    nodes = {node.id: node for node in flow.nodes}
    outgoing = {}
    for edge in flow.edges:
        outgoing.setdefault(edge.source_node_id, []).append(edge.target_node_id)
    pairs = set()
    for part in flow.nodes:
        if part.type != "part":
            continue
        pending = list(outgoing.get(part.id, []))
        visited = set()
        while pending:
            node_id = pending.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            if nodes[node_id].type == "department":
                pairs.add((part.id, node_id))
            pending.extend(outgoing.get(node_id, []))
    return sorted(pairs)


@dataclass(frozen=True)
class MaterialRoute:
    material_node_id: str
    department_node_id: str
    part_node_ids: tuple[str, ...]


def flow_adjacency(flow) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    incoming = {node.id: set() for node in flow.nodes}
    outgoing = {node.id: set() for node in flow.nodes}
    for edge in flow.edges:
        incoming[edge.target_node_id].add(edge.source_node_id)
        outgoing[edge.source_node_id].add(edge.target_node_id)
    return incoming, outgoing


def _topological_nodes(incoming, outgoing) -> list[str]:
    indegrees = {key: len(value) for key, value in incoming.items()}
    pending = sorted(key for key, degree in indegrees.items() if not degree)
    ordered = []
    while pending:
        key = pending.pop()
        ordered.append(key)
        for target in sorted(outgoing[key]):
            indegrees[target] -= 1
            if not indegrees[target]:
                pending.append(target)
    return ordered


def _unassembled_cycle_routes(flow) -> list[MaterialRoute]:
    pairs = reachable_department_pairs(flow)
    merge_nodes = {
        node.id
        for node in flow.nodes
        if node.type == "department" and node.department_code in {"laser", "assembly"}
    }
    if any(sum(department == key for part, department in pairs) > 1 for key in merge_nodes):
        raise DomainError(
            "assembly_cycle",
            "包含多配件汇合的流程不能有循环，请明确装配先后顺序",
            "process_flow.edges",
        )
    return [MaterialRoute(part, department, (part,)) for part, department in pairs]


def _merge_materials(node, materials):
    if node.department_code not in {"laser", "assembly"} or len(materials) <= 1:
        return materials
    parts = [part for members in materials.values() for part in members]
    if len(parts) != len(set(parts)):
        raise DomainError(
            "assembly_overlapping_inputs",
            "汇合物料重复包含同一配件，请调整路线",
            "process_flow.nodes",
            node.id,
        )
    return {node.id: tuple(sorted(parts))}


def material_routes(flow) -> list[MaterialRoute]:
    validate_process_flow(flow)
    nodes = {node.id: node for node in flow.nodes}
    incoming, outgoing = flow_adjacency(flow)
    ordered = _topological_nodes(incoming, outgoing)
    if len(ordered) != len(nodes):
        return _unassembled_cycle_routes(flow)
    outputs = {}
    routes = []
    for key in ordered:
        node = nodes[key]
        if node.type == "part":
            outputs[key] = {key: (key,)}
            continue
        materials = {}
        for source in sorted(incoming[key]):
            materials.update(outputs[source])
        materials = _merge_materials(node, materials)
        outputs[key] = materials
        routes.extend(
            MaterialRoute(origin, key, members) for origin, members in sorted(materials.items())
        )
    return routes
